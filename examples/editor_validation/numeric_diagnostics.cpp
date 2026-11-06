#include <plc.hpp>

void scan() {
    plc::clear_arithmetic_error();
    plc::clear_shift_carry();
    plc::clear_index_error();
    plc::i16 decimal = 2450;
    plc::i32 long_decimal = 81234567;
    plc::i16 expected_word = 9296;
    plc::i32 expected_dword = -2128394905;
    if (plc::input(0)) {
        decimal = 9999;
        long_decimal = 99999999;
        expected_word = -26215;
        expected_dword = -1717986919;
    }
    plc::i16 packed = plc::int_to_bcd(decimal);
    plc::i16 decoded = plc::bcd_to_int(packed);
    plc::i32 long_packed = plc::dint_to_bcd(long_decimal);
    plc::i32 long_decoded = plc::bcd_to_dint(long_packed);
    plc::i32 combined = plc::concat_words(packed, 4660);
    plc::i16 raw_sum = plc::add_i16(23241, 21853);
    bool overflow = plc::system(18);
    plc::i16 clamped = raw_sum;
    if (overflow) { clamped = 32767; }
    plc::clear_arithmetic_error();
    plc::i16 rotated = plc::rol_i16(-32768, 1);
    bool rotate_carry = plc::system(17);
    plc::i16 shifted = plc::shr_i16(1, 1);
    bool shift_carry = plc::system(17);
    plc::write_word(140, raw_sum);
    plc::write_word(141, clamped);
    plc::write_word(142, packed);
    plc::write_word(143, decoded);
    plc::write_dword(146, long_packed);
    plc::write_dword(148, long_decoded);
    plc::write_dword(150, combined);
    plc::write_dword(160, combined);
    plc::output(0, decoded == decimal);
    plc::output(1, packed == expected_word);
    plc::output(2, long_packed == expected_dword);
    plc::output(3, long_decoded == long_decimal);
    plc::output(4, plc::low_word(combined) == packed);
    plc::output(5, plc::high_word(combined) == 4660);
    plc::output(6, overflow);
    plc::output(7, raw_sum == -20442 && clamped == 32767);
    plc::output(8, rotated == 1);
    plc::output(9, rotate_carry);
    plc::output(10, shifted == 0);
    plc::output(11, shift_carry);
    plc::output(12, !plc::system(18));
    plc::output(13, plc::concat_words(-20536, 0) == 45000);
    plc::output(14, plc::read_word(160) == packed && plc::read_word(161) == 4660);
    plc::output(15, !plc::system(20));
}
