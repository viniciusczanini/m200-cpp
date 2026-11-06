// Native SDK oracle only: this harness is not restricted application C++.
#include <plc.hpp>
#include <cstdio>

static int signed32(unsigned bits) {
    int value;
    __builtin_memcpy(&value, &bits, sizeof(value));
    return value;
}

static short signed16(unsigned short bits) {
    short value;
    __builtin_memcpy(&value, &bits, sizeof(value));
    return value;
}

// Decimal-corrected increment is independent of the SDK's divide/modulo codec.
static unsigned next_bcd(unsigned bits, int digits) {
    for (int place = 0; place < digits; ++place) {
        const unsigned mask = 15u << (place * 4);
        if ((bits & mask) != (9u << (place * 4))) {
            return bits + (1u << (place * 4));
        }
        bits &= ~mask;
    }
    return bits;
}

int main() {
    for (unsigned raw = 0; raw < 65536u; ++raw) {
        const short value = signed16((unsigned short)raw);
        plc::detail::shift_carry = (raw & 1u) != 0;
        plc::detail::arithmetic_error = (raw & 2u) != 0;
        if (plc::int_to_dint(value) != value) return 1;
        if (plc::concat_words(value, 0) != (int)raw) return 2;
        const long long high = (long long)value * 65536LL;
        if (plc::concat_words(0, value) != high) return 3;
        if (plc::concat_words(value, value) != high + raw) return 4;
        if (plc::detail::shift_carry != ((raw & 1u) != 0) ||
            plc::detail::arithmetic_error != ((raw & 2u) != 0)) return 5;
    }
    unsigned packed = 0;
    for (int value = 0; value < 10000; ++value) {
        plc::detail::shift_carry = (value & 1) != 0;
        plc::detail::arithmetic_error = (value & 2) != 0;
        if (plc::int_to_bcd((short)value) != signed16((unsigned short)packed)) return 6;
        if (plc::bcd_to_int(signed16((unsigned short)packed)) != value) return 7;
        if (plc::detail::shift_carry != ((value & 1) != 0) ||
            plc::detail::arithmetic_error != ((value & 2) != 0)) return 8;
        packed = next_bcd(packed, 4);
    }
    packed = 0;
    for (int value = 0; value < 100000000; ++value) {
        volatile int runtime_value = value;
        plc::detail::shift_carry = (value & 1) != 0;
        plc::detail::arithmetic_error = (value & 2) != 0;
        if (plc::dint_to_bcd(runtime_value) != signed32(packed)) return 9;
        if (plc::bcd_to_dint(signed32(packed)) != value) return 10;
        if (plc::detail::shift_carry != ((value & 1) != 0) ||
            plc::detail::arithmetic_error != ((value & 2) != 0)) return 11;
        packed = next_bcd(packed, 8);
    }
    std::puts("{\"status\":\"pass\",\"word_widen_concat_vectors\":65536,\"bcd_word_vectors\":10000,\"bcd_dword_vectors\":100000000,\"hardware_proof\":false}");
}
