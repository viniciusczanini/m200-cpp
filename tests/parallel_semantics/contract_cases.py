"""Literal cases prepared from lane CONTRACT.md handoffs, still unexecuted."""

from .contracts import frame as F, observation as E, source_case as C


CASES = [
    C("G01_stack_is_a_value_snapshot_not_a_live_alias", ["G01"], ["stack.mps","stack.mrd","stack.mpp"], r'''
void scan(){plc::BooleanStack s;s.push(plc::input(0));plc::write_m(0,!plc::input(0));
 bool a=s.peek();bool b=s.pop();plc::output(0,a);plc::output(1,b);plc::output(2,plc::read_m(0));}
''', [F({0:0}),F({0:1})], {"bits":[0,1,2]}, [E(bits=[0,0,1]),E(bits=[1,1,0])],
      "G01 contract: balanced scan-local BooleanStack snapshots; stack edits must not turn snapshots into operand aliases."),
    C("G01_G09_system_word_bit_alias_and_false_enable", ["G01","G09"], ["bool.ld","bool.s","bool.r","HW.RTC_SYSTEM_WORDS"], r'''
void scan(){plc::write_system_word(114,-32768);
 plc::output(0,plc::read_bit("%SW114:X15"));plc::output(1,plc::read_bit("%SW114:X0"));
 plc::reset_bit("%SW114:X15",false);plc::set_bit("%SW114:X0",true);
 plc::output(2,plc::read_bit("%SW114:X15"));plc::write_word(0,plc::read_system_word(114));}
''', [F()], {"words":[0],"bits":[0,1,2]}, [E([32769],[1,0,1])],
      "G01/G09 contract composition: one shared SW114 image, signed carrier and disabled reset has no effect."),
    C("G02_indeterminate_integer_destinations_recover_only_on_overwrite", ["G02"], ["integer.divide","integer.sqrt"], r'''
void scan(){plc::clear_arithmetic_error();plc::write_word(0,123);
 plc::div_word(0,7,0);plc::output(0,plc::system(18));
 plc::clear_arithmetic_error();plc::write_word(0,9);plc::div_word(1,7,2);
 plc::output(1,plc::system(18));plc::sqrt_word(2,-1);plc::output(2,plc::system(18));
 plc::write_word(2,4);plc::clear_arithmetic_error();plc::output(3,plc::system(18));}
''', [F()], {"words":[0,1,2],"bits":[0,1,2,3]}, [E([9,3,4],[1,0,1,0])],
      "G02 contract: no unspecified value is inspected; S18 clear and complete deterministic overwrite are separate actions."),
    C("G02_floating_status_and_S18_have_independent_recovery", ["G02"], ["float.divide","float.sqrt"], r'''
void scan(){plc::clear_arithmetic_error();plc::clear_floating_status();
 plc::write_real(0,plc::div_f32(1.0f,0.0f));plc::write_word(8,plc::floating_status());
 plc::output(0,plc::system(18));plc::clear_arithmetic_error();
 plc::write_word(9,plc::floating_status());plc::output(1,plc::system(18));
 plc::write_real(2,plc::sqrt_f32(-1.0f));plc::output(2,plc::read_real(2)!=plc::read_real(2));
 plc::write_word(10,plc::floating_status());plc::clear_floating_status();
 plc::write_word(11,plc::floating_status());plc::output(3,plc::system(18));}
''', [F()], {"words":[0,1,8,9,10,11],"bits":[0,1,2,3]}, [E([0,32640,4,4,5,0],[1,0,1,1])],
      "M200 Programming Guide SW17: bit2 division by zero, bit0 invalid/NaN; no NaN payload is invented."),
    C("G02_new_math_order_and_exact_results", ["G02"], ["float.expt","float.deg_to_rad","float.rad_to_deg","float.trunc"], r'''
void scan(){plc::write_real(0,plc::expt_f32(3.0f,-2));plc::write_real(2,plc::expt_f32(10.0f,2));
 plc::write_real(4,plc::deg_to_rad_f32(180.0f));plc::write_real(6,plc::rad_to_deg_f32(0.0f));
 plc::write_dword(8,plc::trunc_i32(-3.9f));}
''', [F()], {"words":[0,1,2,3,4,5,6,7,8,9]}, [E([0,49408,0,17536,4059,16457,0,0,65533,65535])],
      "G02 EXPT exponent-first contract; exact powers and binary32 pi reference. Host transcendental precision remains a local model."),
    C("G03_conversion_recovery_preserves_carry_and_does_not_resurrect_bad_bits", ["G03","G02"], ["convert.bti"], r'''
plc::ConversionRecovery recovery{};
void scan(){plc::clear_arithmetic_error();plc::write_word(5,plc::shl_i16(-32768,1));
 plc::store_bcd_to_int(0,-1);plc::output(0,plc::system(18));
 plc::clear_arithmetic_error();plc::output(1,plc::system(18));
 plc::write_word(0,99);plc::store_bcd_to_int(2,4660);
 plc::output(2,plc::system(18));plc::output(3,plc::system(17));}
''', [F()], {"words":[0,2],"bits":[0,1,2,3]}, [E([99,1234],[1,0,0,1])],
      "G03 recover contract; invalid BCD result is deliberately never read; valid overwrite restores determinate storage."),
    C("G04_table_stride_extrema_search_and_equal_sentinel", ["G04"], ["table.sum_arr","table.min_arr","table.max_arr","table.occur_arr","table.find_eqr","table.find_gtr","table.find_ltr","table.equal_arr"], r'''
void scan(){plc::write_dword(40,-3);plc::write_dword(42,7);plc::write_dword(44,7);plc::write_dword(46,0);
 plc::write_word(48,12345);plc::write_dword(0,plc::sum_arr(plc::dword_table(40,4)));
 plc::write_dword(2,plc::min_arr(plc::dword_table(40,4)));plc::write_dword(4,plc::max_arr(plc::dword_table(40,4)));
 plc::write_word(6,plc::occur_arr(plc::dword_table(40,4),7));
 plc::write_word(7,plc::find_eqr(plc::dword_table(40,4),7));
 plc::write_word(8,plc::find_gtr(plc::dword_table(40,4),7));
 plc::write_word(9,plc::find_ltr(plc::dword_table(40,4),0));
 plc::write_word(10,plc::equal_arr(plc::dword_table(40,4),plc::dword_table(40,4)));}
''', [F()], {"words":[0,1,2,3,4,5,6,7,8,9,10,48]}, [E([11,0,65533,65535,7,0,2,1,65535,0,65535,12345])],
      "Generic pp85-89; stride2, first rank0, missing/equal sentinel-1. Guard word is outside the source table."),
    C("G04_maximum_255_elements_uses_element_count_not_words", ["G04"], ["assign.table","table.sum_arr","table.occur_arr","table.find_eqr"], r'''
void scan(){plc::table_fill(plc::dword_table(40,255),0);plc::write_dword(40,-7);plc::write_dword(548,12);
 plc::write_word(550,23456);plc::write_dword(0,plc::sum_arr(plc::dword_table(40,255)));
 plc::write_word(2,plc::occur_arr(plc::dword_table(40,255),0));plc::write_word(3,plc::find_eqr(plc::dword_table(40,255),12));}
''', [F()], {"words":[0,1,2,3,550]}, [E([5,0,253,254,23456])],
      "Generic table L maximum255; literal first/last positions and253 zero elements expose stride and off-by-one errors."),
    C("G04_sort_direction_and_table_copy", ["G04"], ["table.sort_arr","assign.table"], r'''
void scan(){plc::write_dword(40,4);plc::write_dword(42,-2);plc::write_dword(44,4);plc::write_dword(46,0);
 if(plc::input(0)){plc::sort_arr(-1,plc::dword_table(40,4));}else{plc::sort_arr(1,plc::dword_table(40,4));}
 plc::table_copy(plc::dword_table(0,4),plc::dword_table(40,4));}
''', [F({0:0}),F({0:1})], {"words":list(range(8))}, [E([65534,65535,0,0,4,0,4,0]),E([4,0,4,0,0,0,65534,65535])],
      "Generic pp84/91: positive ascending, negative descending; duplicate equality and signed order are independent literals."),
    C("G04_exact_self_swap_preserves_neighbor_words", ["G04"], ["table.swap"], r'''
void scan(){plc::write_word(0,4660);plc::write_word(1,-32767);plc::write_word(2,-7);
 plc::swap(plc::word_table(0,2),plc::word_table(0,2));}
''', [F()], {"words":[0,1,2]}, [E([13330,384,65529])],
      "Generic p96 byte swap; G04 explicitly supports exact self alias, not partial overlapping native copies."),
    C("G04_ASCII_published_words_expose_byte_order_conflict", ["G04"], ["ascii.ascii_to_int"], r'''
void scan(){plc::write_word(20,14642);plc::write_word(21,12595);plc::write_word(22,8248);plc::write_word(23,14458);
 plc::clear_arithmetic_error();plc::write_word(0,plc::ascii_to_int(plc::word_table(20,4)));plc::output(0,plc::system(18));
 plc::clear_arithmetic_error();plc::write_word(1,plc::ascii_to_int(plc::word_table(22,4)));plc::output(1,plc::system(18));
 plc::clear_arithmetic_error();plc::write_word(2,plc::ascii_to_int(plc::word_table(23,4)));plc::output(2,plc::system(18));}
''', [F()], {"words":[0,1,2],"bits":[0,1,2]}, [E([29318,8,0],[0,0,1])],
      "Generic pp74-75 literal example. It contradicts high-byte-first prose; values are preserved rather than regenerated by a host parser."),
    C("G04_INT_TO_ASCII_published_negative_pattern_and_canaries", ["G04"], ["ascii.int_to_ascii"], r'''
void scan(){plc::write_word(19,111);plc::write_word(24,222);
 plc::int_to_ascii(plc::word_table(20,4),-12369);}
''', [F()], {"words":[19,20,21,22,23,24]}, [E([111,12589,13106,14646,13,222])],
      "Generic p76 exact example: words312D,3332,3936,000D. Both external canaries stay outside the four-word output."),
    C("G04_DINT_ASCII_minimum_roundtrip_is_not_UNSIGNED", ["G04","G03"], ["ascii.dint_to_ascii","ascii.ascii_to_dint"], r'''
void scan(){plc::write_word(19,111);plc::write_word(26,222);
 plc::dint_to_ascii(plc::word_table(20,6),-2147483647-1);
 plc::write_dword(0,plc::ascii_to_dint(plc::word_table(20,6)));}
''', [F()], {"words":[0,1,19,20,21,22,23,24,25,26]}, [E([0,32768,111,12845,13361,13367,13112,13366,3384,222])],
      "Generic pp79-81; hand-packed '-2147483648'+CR, six words, signed minimum and external canaries."),
    C("G04_strings_terminator_lengths_and_first_different_rank", ["G04"], ["string.literal","string.length","string.concat","string.equal_str"], r'''
void scan(){plc::string_assign(plc::word_table(20,2),"AB");plc::string_assign(plc::word_table(30,2),"CD");
 plc::concat(plc::word_table(40,3),plc::word_table(20,2),plc::word_table(30,2));
 plc::write_word(0,plc::length(plc::word_table(40,3)));
 plc::write_word(1,plc::equal_str(plc::word_table(20,2),plc::word_table(20,2)));
 plc::write_word(2,plc::equal_str(plc::word_table(20,2),plc::word_table(30,2)));}
''', [F()], {"words":[0,1,2,40,41]}, [E([4,65535,0,16961,17475])],
      "Operating Guide pp82-86: explicit CR-terminated strings, first differing character rank0, equal sentinel-1; unused trailing padding is not asserted."),
    C("G04_concat_capacity_replaces_last_character_and_sets_S28", ["G04"], ["string.concat"], r'''
void scan(){plc::clear_string_error();plc::write_word(39,111);plc::write_word(42,222);
 plc::string_assign(plc::word_table(20,2),"AB");plc::string_assign(plc::word_table(30,2),"CD");
 plc::concat(plc::word_table(40,2),plc::word_table(20,2),plc::word_table(30,2));plc::output(0,plc::system(28));}
''', [F()], {"words":[39,40,41,42],"bits":[0]}, [E([111,16961,3395,222],[1])],
      "Operating Guide p85 stages2-5: full four-byte destination becomes ABC+CR, not an unterminated ABCD."),
    C("G04_lookup_linear_result_is_in_Y_not_status", ["G04"], ["table.lkup"], r'''
void scan(){plc::write_real(0,5.0f);plc::write_real(2,-99.0f);
 plc::write_real(4,0.0f);plc::write_real(6,0.0f);plc::write_real(8,10.0f);plc::write_real(10,20.0f);
 plc::write_real(12,20.0f);plc::write_real(14,30.0f);
 plc::write_word(20,plc::lkup(plc::real_table(0,8),8));}
''', [F()], {"words":[2,3,20]}, [E([0,16672,0])],
      "Generic pp92-94: three XY pairs, size8, X5 gives Y10 at MF2; returned status0 is a different cell."),
    C("G04_float_table_mean_uses_all_elements", ["G04"], ["table.mean","table.sum_arr"], r'''
void scan(){plc::write_real(40,1.0f);plc::write_real(42,2.0f);plc::write_real(44,3.0f);plc::write_real(46,10.0f);
 plc::write_real(0,plc::mean(plc::real_table(40,4)));plc::write_real(2,plc::sum_arr(plc::real_table(40,4)));}
''', [F()], {"words":[0,1,2,3]}, [E([0,16512,0,16768])],
      "Generic pp85/95; exact binary32 mean4 and sum16 avoid host transcendental/rounding ambiguity."),
    C("G10_invalid_signed_indices_preserve_ordinary_output_image", ["G10"], ["io.read_imm_in","io.write_imm_out"], r'''
void scan(){plc::output(0,true);plc::write_word(0,plc::read_imm_in(-1));plc::write_word(1,plc::read_imm_in(24));
 plc::write_word(2,plc::write_imm_out(-1));plc::write_word(3,plc::write_imm_out(16));}
''', [F()], {"words":[0,1,2,3],"bits":[0]}, [E([1,1,3,3],[1])],
      "Generic pp97-98 codes1/3; G10 contract explicitly handles negative signed carriers as out-of-range, with no successful physical transport."),
]
