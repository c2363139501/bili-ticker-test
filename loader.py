"""
bili_Ticker_test 远程加载启动器
- 激活码验证 + 设备绑定
- 从虚拟主机下载核心代码 core.zip
- 解压到临时目录运行，退出后自动清理
用法: python loader.py [--config-file xxx.json]
"""
from __future__ import annotations

import atexit
import base64
import hashlib
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import uuid
import zipfile

import requests

# ============ 配置 ============
API_ACTIVATE = "http://ser910228246366.ceshi123123.psyidc.com/activate.php"
API_CORE = API_ACTIVATE.replace("activate.php")
# ==============================

# 兼容 PyInstaller 打包：exe 模式下用 sys.executable 所在目录，脚本模式用 __file__ 所在目录
if getattr(sys, "frozen", False):
    LOADER_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    LOADER_DIR = os.path.dirname(os.path.abspath(__file__))

KEY_FILE = os.path.join(LOADER_DIR, ".active_key")
_temp_dir: str | None = None
_owns_temp_dir: bool = False  # 当前进程是否创建了临时目录（用于判断是否清理）


def get_device_id() -> str:
    info = f"{platform.node()}{uuid.getnode()}"
    raw = hashlib.md5(info.encode()).hexdigest()[:16]
    return f"B-{raw}"


DEVICE_ID = get_device_id()


def info(msg: str) -> None:
    print(f"[INFO] {msg}")


def success(msg: str) -> None:
    print(f"[SUCCESS] {msg}")


def error(msg: str) -> None:
    print(f"[ERROR] {msg}")


def activate(key: str, action: str = "verify") -> str:
    """action: 'verify' 验证 / 'trial' 申请试用"""
    try:
        data = {"key": key, "device_id": DEVICE_ID, "action": action}
        r = requests.post(API_ACTIVATE, data=data, timeout=10)
        return r.text.strip()
    except Exception:
        return "error"


def cleanup() -> None:
    """退出时清理临时目录（仅当前进程创建的才清理，子进程不清理父进程的临时目录）"""
    global _temp_dir, _owns_temp_dir
    if not _owns_temp_dir:
        return
    if _temp_dir and os.path.isdir(_temp_dir):
        try:
            shutil.rmtree(_temp_dir, ignore_errors=True)
        except Exception:
            pass


def download_and_extract_core(key: str) -> str:
    """从服务器下载 core.zip 并解压到临时目录，返回临时目录路径"""
    global _temp_dir
    info("正在连接服务器获取核心程序...")
    try:
        r = requests.post(
            API_CORE, data={"key": key, "device_id": DEVICE_ID}, timeout=30
        )
    except Exception as e:
        error(f"连接服务器失败: {e}")
        sys.exit(1)

    if r.status_code != 200:
        error(f"服务器拒绝连接 (状态码: {r.status_code})")
        sys.exit(1)

    body = r.text.strip()
    if body.startswith("error"):
        if "expired" in body:
            error("远程验证失败：授权已过期。")
            if os.path.exists(KEY_FILE):
                os.remove(KEY_FILE)
        else:
            error(f"服务器返回错误: {body}")
        sys.exit(1)

    # 尝试 base64 解码，失败则当作原始 zip 数据
    try:
        zip_data = base64.b64decode(body)
        # 验证是否为 zip (PK 头)
        if not zip_data.startswith(b"PK"):
            raise ValueError("not a zip")
    except Exception:
        zip_data = r.content if r.content.startswith(b"PK") else body.encode()

    if not zip_data.startswith(b"PK"):
        error("服务器返回的数据不是有效的 core.zip")
        sys.exit(1)

    # 解压到临时目录
    global _owns_temp_dir
    _temp_dir = tempfile.mkdtemp(prefix="btb_core_")
    _owns_temp_dir = True
    atexit.register(cleanup)

    zip_path = os.path.join(_temp_dir, "core.zip")
    with open(zip_path, "wb") as f:
        f.write(zip_data)

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(_temp_dir)
    os.remove(zip_path)

    main_py = os.path.join(_temp_dir, "main.py")
    if not os.path.isfile(main_py):
        error("核心包中未找到 main.py")
        sys.exit(1)

    success(f"核心程序已加载 (临时目录: {_temp_dir})")
    return _temp_dir


def do_activation() -> str:
    """激活流程，返回有效 key"""
    key = ""
    was_previous_user = False

    # 1. 读取本地密钥
    if os.path.exists(KEY_FILE):
        was_previous_user = True
        with open(KEY_FILE, "r", encoding="utf-8") as f:
            key = f.read().strip()

    # 2. 验证本地密钥
    if key:
        info("正在验证本地激活码...")
        res = activate(key, action="verify")
        if res == "success":
            success("验证通过，正在加载...")
            return key
        elif res == "expired":
            error("激活码已过期。")
        elif res == "used":
            error("该激活码已被其他设备绑定。")
        else:
            error(f"验证失败: {res}")
        key = ""
        if os.path.exists(KEY_FILE):
            os.remove(KEY_FILE)

    # 3. 无有效密钥，进入激活流程
    print("\n===== 需要激活 =====")
    if was_previous_user:
        info("检测到您曾使用过激活码。体验结束后，请输入正式激活码继续使用。")
        choice = "n"
    else:
        choice = input("是否申请 24 小时免费体验？(y/n): ").strip().lower()

    if choice == "y":
        info("正在向服务器申请临时授权...")
        res = activate("", action="trial")
        if res.startswith("success|"):
            parts = res.split("|")
            if len(parts) == 2:
                new_key = parts[1]
                success(f"申请成功！临时激活码: {new_key}")
                key = new_key
                with open(KEY_FILE, "w", encoding="utf-8") as f:
                    f.write(key)
                info("已保存至本地，即将启动程序。")
            else:
                error("服务器返回数据格式错误。")
                sys.exit(1)
        elif "device_already_activated" in res:
            error("该设备已注册过，无法再次申请体验。")
        else:
            error(f"申请失败: {res}")

    # 4. 输入正式激活码
    if not key:
        while True:
            key = input("请输入正式激活码: ").strip()
            if not key:
                error("激活码不能为空。")
                continue
            res = activate(key, action="verify")
            if res == "success":
                success("激活成功！")
                with open(KEY_FILE, "w", encoding="utf-8") as f:
                    f.write(key)
                break
            elif res == "used":
                error("该激活码已被其他设备绑定")
            elif res == "invalid":
                error("激活码无效")
            elif res == "expired":
                error("激活码已过期")
            else:
                error(f"激活失败: {res}")

    return key


def _run_core(core_dir: str) -> None:
    """在当前进程中运行核心代码（兼容 exe 和脚本模式）"""
    # 将核心代码目录加入 sys.path 最前面
    sys.path.insert(0, core_dir)

    # 设置环境变量，让核心代码知道数据目录和自身位置
    os.environ["BTB_ROOT_DIR"] = LOADER_DIR
    os.environ["BTB_MAIN_PY"] = os.path.join(core_dir, "main.py")
    os.environ["BTB_CORE_DIR"] = core_dir

    # 切换工作目录到数据目录，确保相对路径正确
    os.chdir(LOADER_DIR)

    try:
        import main
        main.main()
    except KeyboardInterrupt:
        info("\n用户中断运行")
        sys.exit(0)
    except SystemExit:
        raise
    except Exception as e:
        error(f"程序发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        cleanup()


def main() -> None:
    # 直接运行模式（多开子进程用）：跳过激活，直接运行已解压的核心代码
    if os.environ.get("BTB_DIRECT_RUN") == "1":
        core_dir = os.environ.get("BTB_CORE_DIR", "")
        if core_dir and os.path.isdir(core_dir):
            _run_core(core_dir)
        else:
            error("直接运行模式缺少有效的 BTB_CORE_DIR")
            sys.exit(1)
        return

    print("===== bili_Ticker_test 安全加载器 =====")
    print(f"设备 ID: {DEVICE_ID}")
    print()

    # 激活验证
    key = do_activation()

    # 下载并解压核心代码
    temp_dir = download_and_extract_core(key)

    info("启动程序...")
    print()

    # 进程内运行核心代码（exe 模式下无需独立 Python 解释器）
    _run_core(temp_dir)


if __name__ == "__main__":
    main()
