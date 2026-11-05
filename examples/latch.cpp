#include <plc.hpp>

plc::RisingEdge botao;
plc::Ton bloqueio{500};
bool habilitado = false;

void scan() {
    bool pressionou = botao.update(plc::input(0));
    bool bloqueado = bloqueio.update(plc::input(1));

    if (pressionou) {
        habilitado = !habilitado;
    }
    if (plc::input(2)) {
        habilitado = false;
    }

    plc::output(0, habilitado && !bloqueado);
    plc::output(1, habilitado && plc::clock_ms(1000));
}
