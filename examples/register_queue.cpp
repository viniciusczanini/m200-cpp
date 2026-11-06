#include <plc.hpp>

plc::Fifo fifo{0};
plc::Lifo lifo{1};

void scan() {
    if (plc::input(3)) {
        fifo.set_input(22);
        lifo.set_input(22);
    } else {
        fifo.set_input(11);
        lifo.set_input(11);
    }
    if (plc::input(4)) {
        fifo.set_output(42);
        lifo.set_output(42);
    }
    fifo.update(plc::input(0), plc::input(1), plc::input(2));
    lifo.update(plc::input(0), plc::input(1), plc::input(2));

    plc::output(0, fifo.empty());
    plc::output(1, fifo.full());
    plc::output(2, lifo.empty());
    plc::output(3, lifo.full());
    plc::output(4, fifo.output() == 11);
    plc::output(5, fifo.output() == 22);
    plc::output(6, lifo.output() == 11);
    plc::output(7, lifo.output() == 22);
    plc::output(8, fifo.output() == 42);
    plc::output(9, lifo.output() == 42);
}
