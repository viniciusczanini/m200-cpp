#include "plc.hpp"

// Initial SL1 master profile is supplied by the project template.
// Runtime words 10..12 belong to the application, not compiler scratch.
plc::ReadVar sample{7,plc::Link::Serial1,1,100,plc::Object::HoldingWords,0,2,100};

void scan() {
    sample.set_property(plc::CommProperty::Id,plc::read_word(10));
    sample.set_property(plc::CommProperty::FirstObj,plc::read_word(11));
    sample.set_property(plc::CommProperty::Timeout,plc::read_word(12));
    sample.update(plc::input(0),plc::input(1));
    plc::output(0,sample.done());
    plc::output(1,sample.busy());
    plc::output(2,sample.error());
    plc::write_word(20,sample.comm_error());
    plc::write_dword(22,sample.oper_error());
    plc::write_word(24,sample.property(plc::CommProperty::Id));
}
