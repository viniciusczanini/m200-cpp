#include <plc.hpp>

plc::Clock pisca{500};

void scan() {
    bool ligado = pisca.update(true);
    plc::output(0, ligado);
    plc::output(1, !ligado);
}
