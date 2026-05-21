"""一键运行入口 —— 在 IDLE / VSCode 打开本文件按 F5 即可。

第一次运行会自动装依赖（约 1-2 分钟），之后秒开。
不用动命令行，配置全在下面的「配置区」里改。
"""

# =========================================================================
# 配置区 —— 只改这几行就行
# =========================================================================

# DeepSeek API key （去 https://platform.deepseek.com 注册拿）
# 必填，留空就只抓取不出摘要
DEEPSEEK_API_KEY = ""

# 时间窗口（含两端）。留空 = 自动取过去 7 天
DATE_FROM = ""   # 例如 "2026-05-13"
DATE_TO   = ""   # 例如 "2026-05-20"

# 只跑指定智库（调试用）。留空 = 跑 sources.yaml 里所有启用的源
# 可填多个，逗号分隔。已启用的有：
#   chatham_house, rusi, iris, institut_montaigne, ifo, swp, dgap,
#   elcano, riac, valdai
ONLY_SOURCES = ""   # 例如 "swp,elcano"

# True = 跳过 LLM 摘要（只抓取+渲染，不烧 token，省钱测流水线）
SKIP_SUMMARY = False

# True = 跑完自动用浏览器打开周报 HTML
AUTO_OPEN = True

# =========================================================================
# 以下不用改
# =========================================================================

import importlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def _ensure_deps() -> None:
    required = [
        ("requests", "requests>=2.31"),
        ("yaml", "PyYAML>=6.0"),
        ("lxml", "lxml>=5.0"),
        ("trafilatura", "trafilatura>=2.0"),
        ("dateutil", "python-dateutil>=2.9"),
        ("jinja2", "Jinja2>=3.1"),
    ]
    missing = []
    for mod, pkg in required:
        try:
            importlib.import_module(mod)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"[setup] 首次运行, 安装依赖: {' '.join(missing)}")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", *missing],
        )
        print("[setup] 依赖安装完成\n")


def _write_runtime_env() -> None:
    """把配置区的值写进环境变量, 让 tracker.config 读到。

    不去碰 .env 文件, 这样用户复制粘贴 key 不会意外提交。
    """
    import os
    if DEEPSEEK_API_KEY.strip():
        os.environ["DEEPSEEK_API_KEY"] = DEEPSEEK_API_KEY.strip()


def _build_argv() -> list[str]:
    argv: list[str] = []
    if DATE_FROM.strip() and DATE_TO.strip():
        argv += ["--from", DATE_FROM.strip(), "--to", DATE_TO.strip()]
    if ONLY_SOURCES.strip():
        argv += ["--only", ONLY_SOURCES.strip()]
    if SKIP_SUMMARY:
        argv += ["--no-summary"]
    argv += ["-v"]
    return argv


def _open_latest_report() -> None:
    import webbrowser
    out_dir = ROOT / "output"
    htmls = sorted(out_dir.glob("weekly-*.html"))
    if not htmls:
        print("[done] 未生成报告 (可能本窗口无产出)")
        return
    latest = htmls[-1]
    print(f"\n[done] 周报: {latest}")
    if AUTO_OPEN:
        webbrowser.open(latest.as_uri())
        print("[done] 已用浏览器打开")


def main() -> int:
    _ensure_deps()
    _write_runtime_env()

    if not DEEPSEEK_API_KEY.strip() and not SKIP_SUMMARY:
        print("=" * 60)
        print("⚠  DEEPSEEK_API_KEY 未填, 摘要会跳过 (只抓取+渲染)")
        print("   想出中文摘要, 把 key 填到本文件顶部 DEEPSEEK_API_KEY")
        print("=" * 60)

    from tracker.cli import main as cli_main
    code = cli_main(_build_argv())
    if code == 0:
        _open_latest_report()
    return code


if __name__ == "__main__":
    sys.exit(main())
