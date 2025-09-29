import os
import re
import argparse
from pydub import AudioSegment

def parse_hms_or_seconds(s: str) -> float:
    """支持 123.45、'754' 或 '00:12:34' / '12:34' / '1:02:03.5' 这类格式"""
    s = s.strip()
    if re.match(r"^\d+(\.\d+)?$", s):  # 纯秒
        return float(s)
    parts = s.split(":")
    if len(parts) == 2:  # MM:SS(.ms)
        mm, ss = parts
        return int(mm) * 60 + float(ss)
    if len(parts) == 3:  # HH:MM:SS(.ms)
        hh, mm, ss = parts
        return int(hh) * 3600 + int(mm) * 60 + float(ss)
    raise ValueError(f"无法解析时间格式: {s}")

def hms_from_seconds(x: float) -> str:
    x_int = int(x)
    h, r = divmod(x_int, 3600)
    m, s = divmod(r, 60)
    return f"{h:02d}h{m:02d}m{s:02d}s"

def main():
    parser = argparse.ArgumentParser(description="从长音频截取窗口并按固定时长切片导出")
    parser.add_argument("--input", required=True, help="输入音频文件（建议标准WAV）")
    parser.add_argument("--start", required=True, help="开始时间（秒，或HH:MM:SS）")
    parser.add_argument("--end",   required=True, help="结束时间（秒，或HH:MM:SS）")
    parser.add_argument("--outdir", required=True, help="输出目录（会自动创建子文件夹）")
    parser.add_argument("--name", required=True, help="段名（将作为子文件夹与文件前缀）")
    parser.add_argument("--chunk", type=float, default=15.0, help="切片长度（秒，默认15）")
    parser.add_argument("--drop_last", action="store_true",
                        help="末尾不足一个chunk时丢弃（默认保留）")
    parser.add_argument("--force_format", choices=["wav"], default="wav",
                        help="导出格式，目前推荐wav")
    # 可选统一参数（如需强制规范）
    parser.add_argument("--sr", type=int, default=None, help="强制采样率（如 32000）")
    parser.add_argument("--channels", type=int, default=None, help="强制声道（如 1）")
    parser.add_argument("--width", type=int, default=None, help="强制位宽字节数（2=16bit）")
    args = parser.parse_args()

    # 读取音频
    audio = AudioSegment.from_file(args.input)
    total_ms = len(audio)

    start_sec = parse_hms_or_seconds(args.start)
    end_sec   = parse_hms_or_seconds(args.end)
    assert end_sec > start_sec, "结束时间必须大于开始时间"

    start_ms = max(0, int(round(start_sec * 1000)))
    end_ms   = min(total_ms, int(round(end_sec * 1000)))
    if end_ms <= start_ms:
        raise ValueError("窗口超出音频范围或为空")

    window = audio[start_ms:end_ms]

    # 可选：输出前统一规格
    if args.sr is not None:
        window = window.set_frame_rate(args.sr)
    if args.channels is not None:
        window = window.set_channels(args.channels)
    if args.width is not None:
        window = window.set_sample_width(args.width)

    # 输出目录：outdir/name
    out_root = os.path.join(args.outdir, args.name)
    os.makedirs(out_root, exist_ok=True)

    chunk_ms = int(round(args.chunk * 1000))
    n = 0
    pos = 0
    while pos < len(window):
        nxt = min(pos + chunk_ms, len(window))
        if args.drop_last and (nxt - pos) < chunk_ms:
            break
        seg = window[pos:nxt]

        # 文件名：Name_起点绝对时间_序号.wav（便于回溯）
        start_abs = start_sec + pos / 1000.0
        start_tag = hms_from_seconds(start_abs)
        out_name = f"{args.name}_{start_tag}.{args.force_format}"
        out_path = os.path.join(out_root, out_name)
        seg.export(out_path, format=args.force_format)
        print(f"✅ 保存: {out_path}  ({(nxt-pos)/1000:.2f}s)")
        n += 1
        pos = nxt

    print(f"🎉 完成！共导出 {n} 段 → {out_root}")

if __name__ == "__main__":
    main()
# python slice_audio.py --input "combinedall\SBW1520_20160813_222435_TO_000500.wav" --start 02:00:00 --end 03:30:00 --outdir dataset --name source_domain_1 --chunk 15 --drop_last
