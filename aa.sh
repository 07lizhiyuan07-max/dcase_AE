#!/bin/bash

echo "欢迎来到猜数字游戏 🎮"

while true; do
    # 随机生成 1~10
    number=$(shuf -i 1-10 -n 1)

    echo "我心里想了一个 1~10 的数字，来猜一猜吧！"
    read -p "请输入你的猜测: " guess

    if [[ $guess -eq $number ]]; then
        echo "猜对了 🎉"
    elif [[ $guess -lt $number ]]; then
        echo "小了 😅"
    else
        echo "大了 😆"
    fi

    # 询问是否继续
    read -p "是否继续游戏？(y/n): " choice
    if [[ $choice == "y" || $choice == "Y" ]]; then
        continue   # 回到 while true 开头，再玩一轮
    else
        echo "游戏结束，再见 👋"
        break      # 退出 while true
    fi
done
