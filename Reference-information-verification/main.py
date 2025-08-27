import sys
import traceback
import faulthandler
from datetime import datetime
from qt_frontend import main

# 启用faulthandler以获取更详细的错误信息
faulthandler.enable()


def excepthook(type, value, tb):
    """全局异常处理"""
    error_msg = ''.join(traceback.format_exception(type, value, tb))
    print(f"未捕获的异常: {error_msg}")

    # 将错误信息写入日志文件
    with open("error_log.txt", "a", encoding="utf-8") as f:
        f.write(f"=== {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
        f.write(error_msg)
        f.write("\n\n")

    # 尝试显示错误对话框
    try:
        from PyQt5.QtWidgets import QApplication, QMessageBox
        app = QApplication.instance()
        if app is not None:
            QMessageBox.critical(None, "未处理的异常",
                                 f"程序遇到未处理的异常:\n{str(value)}\n\n详细信息已保存到 error_log.txt")
    except:
        pass

    sys.exit(1)


if __name__ == "__main__":
    # 设置全局异常处理
    sys.excepthook = excepthook

    # 正确的堆栈大小设置方式
    try:
        import ctypes

        # 设置堆栈大小为16MB
        stack_size = 16 * 1024 * 1024  # 16MB
        # 使用ctypes设置线程堆栈大小
        if hasattr(ctypes, 'windll'):
            # 创建一个新的线程属性
            thread_attr = ctypes.c_void_p()
            # 初始化线程属性
            ctypes.windll.kernel32.InitializeThreadpoolEnvironment(ctypes.byref(thread_attr))
            # 设置堆栈大小
            ctypes.windll.kernel32.SetThreadStackGuarantee(ctypes.byref(ctypes.c_ulong(stack_size)))
    except Exception as e:
        print(f"设置堆栈大小失败: {str(e)}")

    # 运行主程序
    main()