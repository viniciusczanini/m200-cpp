#include <plc.hpp>

// G07 API example, not executed or officially validated by this lane.
// Explicit identities avoid hidden renumbering in a composed program.
plc::Ton ready_delay{0, 10, 25};
plc::Pulse accepted_pulse{1, 100, 5};
plc::Tof release_delay{254, 1000, 2};

void scan() {
    bool start = plc::input(0);
    bool reset = plc::input(1);
    bool service = plc::input(2);
    // TON reset is its documented IN=false path.
    bool ready = ready_delay.update(start && !reset);
    // A held true signal generates one TP pulse; it needs a new rising edge
    // after completion. TP has no reset input; do not synthesize one.
    bool pulse = accepted_pulse.update(ready);
    release_delay.execute(start && !reset);
    // A skipped update leaves the timer progressing internally. A conditional
    // call is different from calling update(false).
    if (service) {
        ready_delay.execute(false);
    }
    plc::output(0, ready);
    plc::output(1, pulse);
    plc::output(2, release_delay.done());
    plc::write_word(0, ready_delay.value());
    plc::write_word(1, accepted_pulse.preset());
}
