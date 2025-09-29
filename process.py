import os
import re
from datetime import datetime
from pydub import AudioSegment
import logging

# ============ 基本参数 ============
input_dir = "Data"          # 输入目录
output_dir = "combinedall"     # 输出目录
files_per_group = 200    # 每组合并的文件数量（你之前提到 30个/组）
pattern = r'^SBW1520_(\d{8})_(\d{6})\.wav$'  # 文件名时间戳格式

# 目标音频规范（合并前统一到同一规格，避免后续工具出问题）
TARGET_SR = 32000           # 采样率（按你项目常用 32kHz，如有不同改这里）
TARGET_CHANNELS = 1         # 声道数
TARGET_WIDTH = 2            # 每采样字节数：2=16bit

# ============ Windows 上确保 pydub 能找到 ffmpeg（可选） ============
# from pydub.utils import which
# AudioSegment.converter = which("ffmpeg") or r"C:\ffmpeg\bin\ffmpeg.exe"

# ============ 日志 ============
os.makedirs(output_dir, exist_ok=True)
log_path = os.path.join(output_dir, "combine_log.txt")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(log_path, encoding="utf-8"), logging.StreamHandler()]
)

# ============ 读取兜底：WAV -> RIFF 修复 -> RAW ============
def robust_load_audio(path, raw_sr=TARGET_SR, raw_channels=TARGET_CHANNELS, raw_width=TARGET_WIDTH):
    """
    1) 正常 WAV 读取
    2) 若失败：在文件中查找 'RIFF'，裁剪到 'RIFF' 位置后再读
    3) 若仍失败：按原始 PCM (s16le) 读取
    """
    # 1) 尝试直接读取 WAV
    try:
        return AudioSegment.from_wav(path)
    except Exception as e:
        logging.warning(f"from_wav 失败：{path} | {e}")

    # 2) 查找 'RIFF' 偏移并裁剪
    try:
        with open(path, "rb") as f:
            blob = f.read()
        riff_pos = blob.find(b"RIFF")
        if riff_pos >= 0:
            trimmed_path = path + ".__trimmed__.wav"
            with open(trimmed_path, "wb") as g:
                g.write(blob[riff_pos:])
            try:
                seg = AudioSegment.from_wav(trimmed_path)
                # 清理临时文件
                try:
                    os.remove(trimmed_path)
                except Exception:
                    pass
                return seg
            except Exception as e2:
                logging.warning(f"裁剪后 from_wav 仍失败：{path} | {e2}")
                try:
                    os.remove(trimmed_path)
                except Exception:
                    pass
    except Exception as e:
        logging.warning(f"RIFF 搜索/裁剪失败：{path} | {e}")

    # 3) 原始 PCM 兜底
    try:
        return AudioSegment.from_raw(path, sample_width=raw_width, frame_rate=raw_sr, channels=raw_channels)
    except Exception as e:
        logging.error(f"from_raw 也失败：{path} | {e}")
        raise

def normalize(seg: AudioSegment,
              target_sr=TARGET_SR,
              target_channels=TARGET_CHANNELS,
              target_width=TARGET_WIDTH) -> AudioSegment:
    """统一到同一采样率/声道/位宽"""
    if seg.frame_rate != target_sr:
        seg = seg.set_frame_rate(target_sr)
    if seg.channels != target_channels:
        seg = seg.set_channels(target_channels)
    if seg.sample_width != target_width:
        seg = seg.set_sample_width(target_width)
    return seg

# ============ 收集并按时间排序 ============
all_files = [f for f in os.listdir(input_dir) if f.lower().endswith('.wav')]
file_times = []
skipped_badname = []

for f in all_files:
    m = re.match(pattern, f)
    if not m:
        skipped_badname.append(f)
        continue
    date_str, time_str = m.groups()
    ts = datetime.strptime(f"{date_str}{time_str}", "%Y%m%d%H%M%S")
    file_times.append((f, ts))

file_times.sort(key=lambda x: x[1])
sorted_files = [f for f, _ in file_times]

if skipped_badname:
    logging.warning(f"文件名不匹配而被跳过（{len(skipped_badname)}）例：{skipped_badname[:3]}")

# ============ 分组并合并 ============
failed_files = []
group_index = 0

for i in range(0, len(sorted_files), files_per_group):
    group_files = sorted_files[i:i + files_per_group]
    if not group_files:
        continue

    group_index += 1
    logging.info(f"开始合并 第{group_index}组（{len(group_files)} 个文件）...")

    combined = AudioSegment.silent(duration=0)
    ok_count = 0

    for filename in group_files:
        path = os.path.join(input_dir, filename)
        try:
            seg = robust_load_audio(path)
            seg = normalize(seg)  # 统一规格
            combined += seg
            ok_count += 1
        except Exception:
            failed_files.append(filename)
            logging.error(f"跳过损坏/无法读取：{filename}")

    if ok_count == 0:
        logging.error(f"第{group_index}组全部失败，跳过输出。")
        continue

    # 输出文件名：起止时间
    first = group_files[0]
    last = group_files[ok_count - 1] if ok_count == len(group_files) else group_files[-1]
    # 起始：SBW1520_YYYYMMDD_HHMMSS； 结束只保留时间部分
    first_base = os.path.splitext(first)[0]
    last_match = re.match(pattern, last)
    end_tag = last_match.group(2) if last_match else os.path.splitext(last)[0]

    out_name = f"{first_base}_TO_{end_tag}.wav"
    out_path = os.path.join(output_dir, out_name)
    combined.export(out_path, format="wav")
    logging.info(f"✅ 已创建: {out_path}（成功 {ok_count}/{len(group_files)}）")

# ============ 总结 ============
print("\n🎉 合并完成!")
print(f"⏺ 日志: {log_path}")
if failed_files:
    print(f"⚠️ 有 {len(failed_files)} 个文件失败，如需排查请查看日志；示例：{failed_files[:5]}")
