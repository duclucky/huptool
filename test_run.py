import traceback
import sys
with open("test_out.txt", "w") as f:
    f.write("Starting test\n")
    try:
        import gui
        f.write("gui imported\n")
        app = gui.App()
        f.write("App inited successfully\n")
    except Exception as e:
        f.write(traceback.format_exc())
        f.write("\nException caught!\n")
