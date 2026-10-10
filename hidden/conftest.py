def pytest_terminal_summary(terminalreporter):
    import adapter

    terminalreporter.write_line("API notes: " + "; ".join(f"{k}={v}" for k, v in sorted(adapter.NOTES.items())))
