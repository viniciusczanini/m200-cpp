"""Bind original prepared G09 requests to the frozen, independent host engines.

Only requests reach this module. Literal expectations remain in priority_cases.py.
No production calendar/BCD helper is used to construct expected results; date
formatting below serializes actual observations. No compiler module is imported
until the frozen sequence helper executes the selected backend.
"""
from datetime import datetime

from .g09_adapters import sequence


# Vendor CodeGeneratorService ConversionHelper.ScheduleBlockDaysOfTheWeekMaskBuilder
# adds these exact constants. Cached static CIL is in lanes/G09/vendor-schedule-cil.txt.
DOW = {
    "Monday": 1, "Tuesday": 2, "Wednesday": 4, "Thursday": 8,
    "Friday": 16, "Saturday": 32, "Sunday": 64,
}


def calendar_components(text):
    """Parse a request seed; perform no date advancement or oracle calculation."""
    value = datetime.fromisoformat(text)
    if value.tzinfo is not None or value.microsecond:
        raise ValueError("G09 priority seeds require whole-second local calendar values")
    return [value.year, value.month, value.day, value.hour, value.minute, value.second]


def calendar_text(actual):
    """Format a six-component observation, without computing its expected date."""
    if len(actual) != 6 or any(type(n) is not int for n in actual):
        raise AssertionError("RTC backend calendar observation has an invalid shape")
    return datetime(*actual).isoformat(timespec="seconds")


def snapshot_calendar(words):
    """Decode actual five-word RTC snapshot data, not an expected rollover."""
    if len(words) != 5:
        raise AssertionError("RTC snapshot backend returned a different word count")
    def decimal(word):
        if type(word) is not int or not 0 <= word <= 65535:
            raise AssertionError("RTC snapshot word is not a u16 bit pattern")
        digits = [(word >> shift) & 15 for shift in (12, 8, 4, 0)]
        if any(digit > 9 for digit in digits):
            raise AssertionError("RTC snapshot contains a nondecimal BCD nibble")
        return digits[0] * 1000 + digits[1] * 100 + digits[2] * 10 + digits[3]
    _, seconds, hhmm, mmdd, year = [decimal(word) for word in words]
    return [year, mmdd // 100, mmdd % 100, hhmm // 100, hhmm % 100, seconds]


def bcd_input(value, digits):
    """Encode requested input words only; never called with an expected result."""
    if type(value) is not int or not 0 <= value < 10 ** digits:
        raise ValueError("G09 BCD input is outside its decimal field width")
    result = 0
    for offset in range(digits):
        result |= (value % 10) << (4 * offset)
        value //= 10
    return result


def clock(*, engine, request, repo, work):
    scenario = request["scenario"]
    if scenario == "calendar_rollovers":
        positions = request["positions"]
        if not positions:
            raise ValueError("Calendar rollover request must contain at least one position")
        events = []
        for position in positions:
            events += [
                {"seed": calendar_components(position["clock"])},
                {"advance_ms": position["advance_ms"]},
                {"scan": {}},
            ]
        observations = sequence(
            engine=engine,
            request={
                "source": "#include <plc.hpp>\nvoid scan(){plc::rtc_snapshot(100);}\n",
                "clock": calendar_components(positions[0]["clock"]),
                "observe": {"words": [100, 101, 102, 103, 104]},
                "events": events,
            },
            repo=repo, work=work,
        )
        if len(observations) != len(positions):
            raise AssertionError("Calendar rollover backend returned a different probe count")
        return [calendar_text(snapshot_calendar(row["words"])) for row in observations]

    if scenario == "staged_clock_transaction":
        if request.get("before_commit_snapshot") is not True or request.get("commit_on_S50_falling") is not True:
            raise ValueError("Unbound transaction phases; explicit before/falling-edge probes are required")
        stage = request["stage"]
        values = [
            bcd_input(stage["seconds"], 2),
            bcd_input(stage["hours"], 2) * 256 + bcd_input(stage["minutes"], 2),
            bcd_input(stage["month"], 2) * 256 + bcd_input(stage["day"], 2),
            bcd_input(stage["year"], 4),
        ]
        # Staging and commit both traverse actual source/frontend/VM or SDK API.
        # Input0 stages all four words under S50; input1 causes its falling edge.
        writes = "".join(
            "plc::write_system_word(" + str(index) + "," + str(value if value < 32768 else value - 65536) + ");"
            for index, value in zip(range(50, 54), values)
        )
        source = (
            "#include <plc.hpp>\nvoid scan(){"
            "if(plc::input(0)){plc::write_system(50,true);" + writes + "}"
            "if(plc::input(1)){plc::write_system(50,false);}}\n"
        )
        observations = sequence(
            engine=engine,
            request={
                "source": source,
                "clock": calendar_components(request["clock"]),
                "observe": {"calendar": True, "system_bits": [52]},
                "events": [{"scan": {0: True}}, {"scan": {1: True}}],
            },
            repo=repo, work=work,
        )
        if len(observations) != 2:
            raise AssertionError("Clock transaction backend returned a different phase count")
        return {
            "before": calendar_text(observations[0]["calendar"]),
            "after": calendar_text(observations[1]["calendar"]),
            "S52": observations[1]["system_bits"][0],
        }
    raise ValueError("Unbound G09 priority clock scenario: " + str(scenario))


def hour_minute(text):
    parts = text.split(":")
    if len(parts) != 2 or any(len(p) != 2 or not p.isdigit() for p in parts):
        raise ValueError("Schedule request requires HH:MM")
    hour, minute = map(int, parts)
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError("Schedule request time is outside the documented range")
    return hour, minute


def schedule(*, engine, request, repo, work):
    if request["scenario"] != "two_schedules_shared_output":
        raise ValueError("Unbound G09 priority schedule scenario")
    if len(request["days"]) != 2 or len(request["indices"]) != 2:
        raise ValueError("This prepared schedule request requires two explicit schedules")
    if request["checks"] != ["Monday12:30", "Tuesday12:30", "Wednesday12:30", "both_disabled", "cold_restart"]:
        raise ValueError("Unbound schedule probe order")
    output = request["output"]
    if not output.startswith("%Q0.") or not output[4:].isdigit():
        raise ValueError("Prepared priority schedule probe requires a direct Q0 output")
    output_index = int(output[4:])
    if not 0 <= output_index < 16:
        raise ValueError("Schedule output is outside the target digital bank")
    start_hour, start_min = hour_minute(request["start"])
    end_hour, end_min = hour_minute(request["end"])
    dates = request["date_window"]
    configurations = {}
    for index, day in zip(request["indices"], request["days"]):
        if type(index) is not int or not 0 <= index < 16 or str(index) in configurations:
            raise ValueError("Schedule identities must be distinct native indices0..15")
        configurations[str(index)] = {
            "output": output,
            "start_day": dates["start_day"], "start_month": dates["start_month"],
            "start_hour": start_hour, "start_min": start_min,
            "end_day": dates["end_day"], "end_month": dates["end_month"],
            "end_hour": end_hour, "end_min": end_min,
            "dow": DOW[day],
        }
    events = []
    for check in request["checks"]:
        events.append({"seed": calendar_components(request["check_clocks"][check])})
        if check == "both_disabled":
            events.append({"write_sw": [114, 0]})
        elif check == "cold_restart":
            # Family-only hook; no CPU cold/warm/STOP or physical battery claim.
            events.append({"reset": "cold"})
        events.append({"scan": {}})
    observations = sequence(
        engine=engine,
        request={
            "mode": "schedule_source", "schedules": configurations,
            "clock": calendar_components(request["check_clocks"][request["checks"][0]]),
            "observe": {"bits": [output_index], "system_words": [114]},
            "events": events,
        },
        repo=repo, work=work,
    )
    if len(observations) != len(request["checks"]):
        raise AssertionError("Schedule backend returned a different probe count")
    return [
        {"check": check, "output": row["bits"][0], "SW114": row["system_words"][0]}
        for check, row in zip(request["checks"], observations)
    ]
