from cyclopts import App

app = App()


@app.command
def config():
    pass


@app.command
def doctor(autofix: bool = False):
    from prism.util import Doctor

    Doctor().run(autofix)


@app.command
def cec_test():
    from prism.display.cec import CEC

    cec = CEC()

    result = cec.test()

    print(f"CEC adapter: {result['adapter']}")
    print(f"CEC supported: {result['cec_supported']}")
    print(f"Playback configured: {result['playback_configured']}")

    print("\nDevices:")

    for device in result["devices"]:
        print(f"  {device['logical_address']}: {device['name']}")

    print(f"\nBest device: {result['best_device']}")


app()
