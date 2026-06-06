from PySide6.QtCore import QSettings


def get_settings() -> QSettings:
    return QSettings("Vaven", "XIVDownscaleUtility")
