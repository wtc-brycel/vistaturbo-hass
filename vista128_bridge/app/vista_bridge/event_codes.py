EVENT_DESCRIPTIONS: dict[str, str] = {
    "01": "Fire Alarm",
    "02": "Fire Alarm Restore",
    "03": "Trouble",
    "04": "Trouble Restore",
    "05": "Bypass",
    "06": "Bypass Restore",
    "07": "Close (Arm)",
    "08": "Open (Disarm)",
    "0D": "Manual Trigger Test Report",
    "0E": "Power-Up Report",
    "0F": "Exit Error By User",
    "11": "Duress Alarm",
    "12": "Duress Restore",
    "17": "Remote Close (Arm)",
    "18": "Remote Open (Disarm)",
    "1B": "AC Loss",
    "1C": "AC Restore",
    "1D": "Periodic Test Report",
    "1F": "Exit Error By Zone",
    "21": "Silent Alarm",
    "22": "Silent Alarm Restore",
    "27": "Quick Arm (Close)",
    "29": "System Low Battery",
    "2A": "System Low Battery Restore",
    "2D": "Walk Test",
    "31": "Audible Alarm",
    "32": "Audible Alarm Restore",
    "37": "Keyswitch Close (Arm)",
    "38": "Keyswitch Open (Disarm)",
    "3D": "Walk Test Exit",
    "3E": "Power-Up Report",
    "41": "Perimeter Alarm",
    "42": "Perimeter Alarm Restore",
    "43": "Supervisory Alarm",
    "44": "Supervisory Alarm Restore",
    "47": "Partial Arm",
    "51": "Interior Alarm",
    "52": "Interior Alarm Restore",
    "53": "Expansion Module Tamper",
    "54": "Expansion Module Tamper Restore",
    "63": "RF Expansion Module Supervision",
    "64": "RF Expansion Module Supervision Restore",
    "89": "RF Low Battery",
    "8A": "RF Low Battery Restore",
    "9E": "Recent Close By User",
    "A1": "RF Expansion Module Fail",
    "A2": "RF Expansion Module Fail Restore",
    "A3": "Expansion Module Fail",
    "A4": "Expansion Module Fail Restore",
    "AD": "Program Mode Entry",
    "B1": "24 Hour Auxiliary Alarm",
    "B2": "24 Hour Auxiliary Alarm Restore",
    "B3": "Sensor Tamper",
    "B4": "Sensor Tamper Restore",
    "B7": "Arm STAY",
    "BD": "Program Mode Exit",
    "C1": "Smoke Alarm",
    "C2": "Smoke Alarm Restore",
    "C3": "Fire Trouble",
    "C4": "Fire Trouble Restore",
    "D1": "Waterflow Alarm",
    "D2": "Waterflow Alarm Restore",
    "D3": "Fail To Communicate",
    "D4": "Communication Restore",
    "E1": "Fire Supervisory Alarm",
    "E2": "Fire Supervisory Alarm Restore",
    "E3": "Bell 1 Trouble",
    "E4": "Bell 1 Trouble Restore",
    "F3": "Bell 2 Trouble",
    "F4": "Bell 2 Trouble Restore",
    "F5": "Fault",
    "F6": "Fault Restore",
    "FD": "Fail To Print",
    "FE": "Fail To Print Restore",
}

ALARM_RESTORE_TO_START = {
    "02": "01",
    "12": "11",
    "22": "21",
    "32": "31",
    "42": "41",
    "44": "43",
    "52": "51",
    "B2": "B1",
    "C2": "C1",
    "D2": "D1",
    "E2": "E1",
}
ALARM_START_CODES = set(ALARM_RESTORE_TO_START.values())

BURGLARY_RESTORE_TO_START = {
    "32": "31",  # audible alarm
    "42": "41",  # perimeter alarm
    "52": "51",  # interior alarm
}
BURGLARY_START_CODES = set(BURGLARY_RESTORE_TO_START.values())

AUXILIARY_RESTORE_TO_START = {
    "B2": "B1",  # 24 hour auxiliary alarm
}
AUXILIARY_START_CODES = set(AUXILIARY_RESTORE_TO_START.values())

ZONE_EVENT_TRANSITIONS: dict[str, tuple[str, bool]] = {
    "03": ("trouble", True),
    "04": ("trouble", False),
    "05": ("bypassed", True),
    "06": ("bypassed", False),
    "F5": ("faulted", True),
    "F6": ("faulted", False),
    "89": ("low_battery", True),
    "8A": ("low_battery", False),
    "B3": ("tamper", True),
    "B4": ("tamper", False),
}

DISARM_EVENT_CODES = {"08", "18", "38"}
