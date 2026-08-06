# dupfinder

> 一个零依赖的命令行重复文件查找器 —— 按内容哈希找出重复文件，告诉你能省下多少磁盘空间。

`dupfinder` 递归扫描一个目录，按文件内容的 **SHA-256** 哈希值对文件分组，
找出真正的重复文件（不是只看文件名或大小），并报告删除多余副本后能 reclaim 的空间。

- 🪶 **零依赖**：只用 Python 标准库，Python 3.8+ 即可运行
- 🔒 **默认只读**：只报告，不删任何东西
- 🧠 **两步加速**：先按文件大小分桶，只对"大小相同"的文件做哈希，避免无谓的磁盘读取
- 📦 **可选删除**：`--delete` 在确认后删除每组里多余的副本（每组保留一个）
- 🤖 **JSON 输出**：方便接入脚本或其他工具

## 安装

不需要安装，直接用 Python 运行即可：

```bash
python dupfinder.py <目录>
```

如果想全局可用，可以把它放到 `PATH` 里：

```bash
cp dupfinder.py ~/.local/bin/dupfinder
chmod +x ~/.local/bin/dupfinder
```

## 用法

```bash
# 扫描当前目录，列出重复文件分组
python dupfinder.py .

# 扫描下载目录，只看大于 1 MB 的文件
python dupfinder.py ~/Downloads --min-size 1048576

# 输出 JSON（方便脚本处理）
python dupfinder.py . --json

# 删除多余副本（每组保留第一个，删除前会确认）
python dupfinder.py ~/Downloads --delete

# 删除多余副本且跳过确认（脚本/自动化场景）
python dupfinder.py ~/Downloads --delete --yes
```

## 命令行参数

| 参数 | 说明 |
|------|------|
| `path` | 要扫描的目录，默认当前目录 `.` |
| `--min-size N` | 忽略小于 N 字节的文件 |
| `--json` | 输出机器可读的 JSON |
| `--delete` | 删除每组多余的副本（删除前确认） |
| `--yes` | 配合 `--delete`，跳过确认 |
| `--follow-links` | 跟随符号链接（默认不跟随） |

## 示例输出

```
Found 3 duplicate group(s), 7 files involved.
Reclaimable space: 12.4 MB
============================================================

[1] 3 copies · 5.0 MB each
    ./photos/IMG_001.jpg
    ./backup/IMG_001.jpg
    ./temp/old/IMG_001.jpg

[2] 2 copies · 1.2 MB each
    ./docs/report.pdf
    ./Desktop/report.pdf
...
```

## 工作原理

1. **按大小分桶**：遍历目录，把相同大小的文件归到一组。大小都不同的文件不可能重复，直接排除。
2. **按内容哈希**：只对"大小相同"的候选文件计算 SHA-256。哈希相同的文件内容必然相同。
3. **报告 / 清理**：输出重复分组与可节省空间；`--delete` 时每组保留第一个文件，删除其余副本。

## 许可证

[MIT](LICENSE)
