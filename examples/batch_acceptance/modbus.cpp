#include <plc.hpp>

plc::ReadVar reader{0, plc::Link::Serial1, 1, 10, plc::Object::DiscreteInputs, 0, 2, 100};
plc::WriteVar writer{0, plc::Link::Serial1, 1, 10, plc::Object::Coils, 0, 2, 110};
plc::WriteReadVar exchange{0, plc::Link::Serial1, 1, 10, 0, 2, 110, 10, 2, 120};

void scan() {
    bool read_execute = plc::input(1) && !plc::input(3) && !plc::input(4);
    bool write_execute = plc::input(1) && plc::input(3) && !plc::input(4);
    bool exchange_execute = plc::input(1) && plc::input(4);
    reader.update(read_execute, plc::input(2));
    writer.update(write_execute, plc::input(2));
    exchange.update(exchange_execute, plc::input(2));
    plc::output(0, reader.done());
    plc::output(1, reader.busy());
    plc::output(2, reader.error());
    plc::output(3, reader.aborted());
    plc::output(4, writer.done());
    plc::output(5, writer.busy());
    plc::output(6, writer.error());
    plc::output(7, writer.aborted());
    plc::output(8, exchange.done());
    plc::output(9, exchange.busy());
    plc::output(10, exchange.error());
    plc::output(11, exchange.aborted());
    plc::write_word(10, reader.comm_error());
    plc::write_dword(12, reader.oper_error());
    plc::write_word(20, writer.comm_error());
    plc::write_dword(22, writer.oper_error());
    plc::write_word(30, exchange.comm_error());
    plc::write_dword(32, exchange.oper_error());
}
