#include <plc.hpp>

// Ethernet index1 must exist in the TM200CE40T template's remote servers.
// Simulation does not contact an endpoint unless a transport is injected.
plc::ReadVar remote{plc::Link::Ethernet, 1, 100,
                    plc::Object::HoldingWords, 0, 2, 100};

void scan() {
    // Execute needs false->true; initial TRUE in RUN is not an edge.
    bool done = remote.update(plc::input(0), false);
    plc::output(0, done);
    plc::output(1, remote.busy());
    plc::output(2, remote.error());
    if (done) {
        plc::output(3, plc::read_word(100) > 0);
    }
}
