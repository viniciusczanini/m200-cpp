"""Hand-derived snapshots and independent mathematical stress references.

Prepared, not executed. Local policies are labelled separately from primary
rules; these cases never establish editor or physical-controller compatibility.
"""

from dataclasses import replace

from .contracts import frame as F, observation as E, source_case as C


def _pending_native_reset_history(case):
    # Retain the original request and premature literal oracle for audit/native
    # qualification. The existing discovery raises PendingOracleError before
    # adapter invocation, so these literals cannot acquire a semantic PASS.
    return replace(
        case,
        oracle_status="pending_native_reset_history",
        basis="PENDING native reset/history qualification; original preliminary oracle retained: " + case.basis,
        notes=case.notes + (
            "Native final-batch plan: preserve the original eight frames, including active CD on frame7 immediately followed by exclusive reset on frame8 (one-based).",
            "Observe %SC7.0, %SC7.1, %SC7.2, %SC7.255 and CU/CD request histories across the collision; determine reset/history priority before replacing the retained preliminary expected trace.",
        ),
    )


CASES = [
    C("G01_repeated_native_edges_share_scan_event", ["G01"], ["bool.ldr", "bool.ldf"], r'''
void scan(){
 bool a=plc::input_rising(0);bool b=plc::input_rising(0);
 bool c=plc::input_falling(0);bool d=plc::input_falling(0);
 plc::output(0,a);plc::output(1,b);plc::output(2,c);plc::output(3,d);
}
''', [F({0:v}, 0) for v in [False, True, True, False, False]], {"bits":[0,1,2,3]},
      [E(bits=r) for r in [(0,0,0,0),(1,1,0,0),(0,0,0,0),(0,0,1,1),(0,0,0,0)]],
      "Existing native-edge scan-image contract; startup/STOP/warm reset are separate unresolved events."),
    C("G01_expression_edges_follow_calls_not_scan_count", ["G01"], ["bool.expression_rising", "bool.expression_falling"], r'''
void scan(){
 for(plc::i16 iteration=0;iteration<2;iteration=plc::add_i16(iteration,1)){
  bool rising=plc::rising(0,plc::input(0));
  bool falling=plc::falling(0,plc::input(0));
  if(iteration==0){plc::output(0,rising);plc::output(2,falling);}
  else{plc::output(1,rising);plc::output(3,falling);}
 }
}
''', [F({0:v},0) for v in [False,True,True,False,False]], {"bits":[0,1,2,3]},
      [E(bits=r) for r in [(0,0,0,0),(1,0,0,0),(0,0,0,0),(0,0,1,0),(0,0,0,0)]],
      "Explicit existing per-call expression-edge policy, independent of native contact sampling."),
    C("G01_skipped_expression_history_and_inactive_side_effect", ["G01","G02"], ["bool.expression_rising","integer.add"], r'''
void scan(){
 plc::output(0,false);
 if(plc::input(1)){plc::output(0,plc::rising(3,plc::input(0)));}
 plc::clear_arithmetic_error();
 bool v=plc::input(2)&&plc::add_i16(32767,1)<0;
 plc::output(1,v);plc::output(2,plc::system(18));
}
''', [F(v,0) for v in [{0:1},{0:1,1:1},{0:1,1:1},{0:0},{0:1,1:1,2:1},{0:0,1:1}]],
      {"bits":[0,1,2]}, [E(bits=r) for r in [(0,0,0),(1,0,0),(0,0,0),(0,0,0),(0,1,1),(0,0,0)]],
      "Per-call history and C++ short-circuit effects; hidden false calls change the first/last pulses."),
    C("G02_overflow_snapshots_and_explicit_recovery_order", ["G02"], ["integer.add","bits.shl","bits.shr"], r'''
void scan(){
 plc::clear_arithmetic_error();plc::clear_shift_carry();
 bool before=plc::system(18);plc::write_word(0,plc::add_i16(32767,1));
 bool captured=plc::system(18);plc::write_word(1,plc::add_i16(1,2));
 bool sticky=plc::system(18);plc::clear_arithmetic_error();
 plc::write_word(2,plc::shl_i16(-32768,1));bool left=plc::system(17);
 plc::write_word(3,plc::shr_i16(2,1));bool right=plc::system(17);
 plc::output(0,before);plc::output(1,captured);plc::output(2,sticky);
 plc::output(3,plc::system(18));plc::output(4,left);plc::output(5,right);
}
''', [F()], {"words":[0,1,2,3],"bits":[0,1,2,3,4,5],"flags":[17,18]},
      [E([32768,3,0,1],[0,1,1,0,1,0],{"17":False,"18":False})],
      "Generic pp55-58 plus explicit existing sticky-overflow/modular-result local policy."),
    C("G02_dword_word_alias_reads_are_ordered_snapshots", ["G02","G03"], ["assign.scalar","convert.lw","convert.hw"], r'''
void scan(){
 plc::write_dword(0,65538);plc::i16 old=plc::read_word(0);
 plc::write_word(1,-1);plc::i32 changed=plc::read_dword(0);
 plc::write_word(2,old);plc::write_word(3,plc::low_word(changed));
 plc::write_word(4,plc::high_word(changed));
}
''', [F()], {"words":[0,1,2,3,4]}, [E([2,65535,2,2,65535])],
      "Generic pp29-30 overlapping MW/MD storage and low/high word bit patterns."),
    C("G02_signed_division_remainder_and_i32_boundary", ["G02"], ["integer.divide","integer.rem","integer.abs"], r'''
void scan(){
 plc::clear_arithmetic_error();
 plc::write_word(0,plc::div_i16(-7,3));plc::write_word(1,plc::rem_i16(-7,3));
 plc::write_word(2,plc::div_i16(7,-3));plc::write_word(3,plc::rem_i16(7,-3));
 plc::write_dword(4,plc::abs_i32(-2147483648));
 plc::output(0,plc::system(18));
}
''', [F()], {"words":[0,1,2,3,4,5],"bits":[0]}, [E([65534,65535,65534,1,0,32768],[1])],
      "Signed truncation toward zero, remainder sign of dividend; ABS minimum is labelled local modular policy."),
    C("G03_bcd_word_order_and_constant_boundaries", ["G03"], ["convert.bti","convert.itb","convert.concatw","convert.dword"], r'''
void scan(){
 plc::write_word(0,plc::bcd_to_int(0));plc::write_word(1,plc::bcd_to_int(-26215));
 plc::write_word(2,plc::int_to_bcd(9999));plc::write_dword(4,plc::concat_words(-1,1));
 plc::write_dword(6,plc::int_to_dint(-1));plc::write_dword(8,plc::dint_to_bcd(99999999));
}
''', [F()], {"words":[0,1,2,4,5,6,7,8,9]}, [E([0,9999,39321,65535,1,65535,65535,39321,39321])],
      "Generic pp58-60; CONCATW low-first. Negative DWORD sign extension remains existing unverified local policy."),
    C("G03_real_ties_and_exact_binary32_integer_boundary", ["G03"], ["convert.real_to_int","convert.real_to_dint","convert.dint_to_real"], r'''
void scan(){
 plc::write_word(0,plc::real_to_int(2.5f));plc::write_word(1,plc::real_to_int(3.5f));
 plc::write_word(2,plc::real_to_int(-2.5f));plc::write_word(3,plc::real_to_int(-3.5f));
 plc::write_dword(4,plc::real_to_dint(plc::dint_to_real(16777217)));
}
''', [F()], {"words":[0,1,2,3,4,5]}, [E([2,4,65534,65532,0,256])],
      "Existing ties-to-even local conversion policy; binary32 exactly distinguishes 2^24 from 2^24+1."),
    C("G05_loop_alias_and_early_return_preserve_prior_effects", ["G05","G02"], ["control.for","control.end","assign.scalar"], r'''
void scan(){
 plc::write_word(0,0);plc::write_word(1,0);plc::write_word(2,99);
 plc::i16 i=0;
 while(i<4){
  plc::write_word(0,plc::add_i16(plc::read_word(0),i));
  if(plc::input(0)&&i==2){plc::write_word(1,7);return;}
  i=plc::add_i16(i,1);
 }
 plc::write_word(2,55);
}
''', [F({0:0}),F({0:1}),F({0:0})], {"words":[0,1,2]}, [E([6,0,55]),E([3,7,99]),E([6,0,55])],
      "C++ source loop/return semantics, with no claim that a lowered loop preserves native FOR spelling."),
    C("G06_two_stateful_leaves_repeated_calls_share_instances", ["G06","G08"], ["control.subroutine","fb.c"], r'''
plc::Counter a{0,99};plc::Counter b{254,99};
void leaf_a(){a.count_up(false);a.count_up(true);plc::write_word(1,b.value());}
void leaf_b(){b.count_up(false);b.count_up(true);}
plc::Subroutine first{0,leaf_a,"A",2};plc::Subroutine last{63,leaf_b,"B",9};
void scan(){first.call(true);last.call(plc::input(0));first.call(true);
 plc::write_word(0,a.value());plc::write_word(2,b.value());}
''', [F({0:0}),F({0:1}),F({0:1})], {"words":[0,1,2]}, [E([2,0,0]),E([4,1,1]),E([6,2,2])],
      "G06 contract: global shared state and exact synchronous call order; counter rising actions use explicit per-call policy."),
    C("G07_two_timers_have_independent_bases_and_reset", ["G07"], ["fb.tm"], r'''
plc::Ton a{0,10,2};plc::Ton b{6,10,3};
void scan(){bool x=a.update(plc::input(0));bool y=b.update(plc::input(1));
 plc::write_word(0,a.value());plc::write_word(1,b.value());plc::output(0,x);plc::output(1,y);}
''', [F({0:1,1:1},9),F({0:1,1:1},1),F({0:1,1:1},10),F({1:1},10),F({0:1,1:1},20),F({0:1,1:1},0)],
      {"words":[0,1],"bits":[0,1]}, [E([0,0],[0,0]),E([0,0],[0,0]),E([1,1],[0,0]),E([0,2],[0,0]),E([0,3],[0,1]),E([2,3],[1,1])],
      "Generic timer rules and activation-relative local tick policy; timestamps are 0,9,10,20,30,50ms."),
    C("G07_pulse_and_off_delay_do_not_share_completion", ["G07"], ["fb.tm"], r'''
plc::Pulse pulse{1,10,2};plc::Tof off{2,10,2};
void scan(){bool x=pulse.update(plc::input(0));bool y=off.update(plc::input(0));
 plc::write_word(0,pulse.value());plc::write_word(1,off.value());plc::output(0,x);plc::output(1,y);}
''', [F({0:v},10) for v in [1,1,0,0,0,1]], {"words":[0,1],"bits":[0,1]},
      [E([0,0],[1,1]),E([1,0],[1,1]),E([0,0],[0,1]),E([0,1],[0,1]),E([0,2],[0,0]),E([0,0],[1,1])],
      "Existing local TP inactive-V reset and TOF timing policy, independently hand-timed."),
    C("G08_fifo_lifo_alias_source_is_not_internal_storage", ["G08","G02"], ["fb.r","assign.scalar"], r'''
plc::Fifo fifo{0};plc::Lifo lifo{3};
void scan(){if(plc::input(4)){plc::write_word(0,22);}else{plc::write_word(0,11);}
 fifo.set_input(plc::read_word(0));lifo.set_input(plc::read_word(0));plc::write_word(0,99);
 fifo.update(plc::input(3),plc::input(1),plc::input(2));
 lifo.update(plc::input(3),plc::input(1),plc::input(2));
 plc::write_word(1,fifo.output());plc::write_word(2,lifo.output());
 plc::output(0,fifo.empty());plc::output(1,lifo.empty());}
''', [F(v) for v in [{3:1},{1:1},{4:1},{1:1,4:1},{},{2:1},{},{2:1}]],
      {"words":[0,1,2],"bits":[0,1]}, [E([99,0,0],[1,1]),E([99,0,0],[0,0]),E([99,0,0],[0,0]),E([99,0,0],[0,0]),E([99,0,0],[0,0]),E([99,11,22],[0,0]),E([99,11,22],[0,0]),E([99,22,11],[1,1])],
      "Generic pp141-146; source MW overwritten after data snapshot, before native queue update."),
    C("G08_sbr_documentary_safe_shifts_and_held_requests", ["G08"], ["fb.sbr"], r'''
plc::ShiftBitRegister shift{7};
void scan(){if(plc::system(13)){shift.set_bit(1,true);}
 if(plc::input(3)){shift.set_bit(3,true);}
 shift.update(plc::input(0),plc::input(1),plc::input(2));
 plc::output(0,shift.bit(0));plc::output(1,shift.bit(1));plc::output(2,shift.bit(2));
 plc::output(3,shift.bit(3));plc::output(4,shift.bit(15));}
''', [F(v) for v in [{},{1:1},{1:1,3:1},{1:1},{2:1},{}]], {"bits":[0,1,2,3,4]},
      [E(bits=r) for r in [(0,1,0,0,0),(0,0,1,0,0),(0,0,1,1,0),(0,0,1,1,0),(0,1,1,0,0),(0,1,1,0,0)]],
      "Generic pp153-155. Vacated endpoints are already zero; ambiguous fill/collisions are deliberately separate error cases."),
    _pending_native_reset_history(C("G08_sc_middle_steps_and_exclusive_reset", ["G08"], ["fb.sc"], r'''
plc::StepCounter step{7};
void scan(){plc::write_word(0,123);step.update(plc::input(0),plc::input(1),plc::input(2));
 plc::output(0,step.bit(0));plc::output(1,step.bit(1));plc::output(2,step.bit(2));plc::output(3,step.bit(255));}
''', [F(v) for v in [{},{1:1},{1:1},{},{1:1},{},{2:1},{0:1}]], {"words":[0],"bits":[0,1,2,3]},
      [E([123],r) for r in [(1,0,0,0),(0,1,0,0),(0,1,0,0),(0,1,0,0),(0,0,1,0),(0,0,1,0),(0,1,0,0),(1,0,0,0)]],
      "Generic pp155-158; middle transitions only, no guessed endpoint or ambiguous one-hot write.")),
    C("G08_sc_middle_steps_neutral_full_pins_before_exclusive_reset", ["G08"], ["fb.sc"], r'''
plc::StepCounter step{7};
void scan(){
 plc::write_word(0,123);
 step.update_pins(7,plc::input(0),plc::input(1),plc::input(2));
 plc::output(0,step.bit(0));plc::output(1,step.bit(1));
 plc::output(2,step.bit(2));plc::output(3,step.bit(255));
}
''', [F({}),F({1:1}),F({}),F({1:1}),F({}),F({2:1}),F({}),F({0:1}),F({}),F({1:1})],
      {"words":[0],"bits":[0,1,2,3]},
      [E([123],(1,0,0,0)),E([123],(0,1,0,0)),E([123],(0,1,0,0)),
       E([123],(0,0,1,0)),E([123],(0,0,1,0)),E([123],(0,1,0,0)),
       E([123],(0,1,0,0)),E([123],(1,0,0,0)),E([123],(1,0,0,0)),E([123],(0,1,0,0))],
      "Generic pp155-158 and final G08 contract: interior steps0->1->2->1; an executed full-pin neutral call releases CD before exclusive reset to0, then neutral and fresh CU reach1. Hand-written literal oracle; local cold/history policy, not native reset-collision evidence.",
      notes=("Separate prepared safe case. The original immediate-CD/reset case remains pending and discoverable; no oracle from that collision is promoted to PASS.",)),
    C("G08_drum_cams_update_on_step_change_not_every_call", ["G08"], ["fb.dr"], r'''
plc::Drum drum{0,3,plc::DrumCam{0,plc::DrumOutput::Memory,10,2},plc::DrumCam{1,plc::DrumOutput::Output,2,4}};
void scan(){if(plc::input(2)){drum.set_step(2);}
 if(!plc::input(3)){drum.update(plc::input(0),plc::input(1));}
 if(plc::input(4)){plc::output(2,false);}
 plc::write_word(0,drum.step());plc::output(0,drum.full());plc::output(1,plc::read_m(10));}
''', [F(v) for v in [{0:1},{},{1:1},{1:1},{},{1:1},{3:1,4:1},{3:1},{},{1:1},{2:1}]],
      {"words":[0],"bits":[0,1,2]}, [E(w,b) for w,b in [([0],[0,0,0]),([0],[0,0,0]),([1],[0,1,0]),([1],[0,1,0]),([1],[0,1,0]),([2],[1,0,1]),([2],[1,0,0]),([2],[1,0,0]),([2],[1,0,0]),([0],[0,0,0]),([2],[1,0,1])]],
      "Generic pp147-151: cams update on changed step; unwired application writes during skipped calls are not repaired each scan."),
    C("G09_rtc_simultaneous_read_write_has_explicit_error", ["G09"], ["fb.rtc"], r'''
plc::Rtc rtc{0,1,1,2026,0,0,0};
void scan(){rtc.update(true,true,true);plc::write_word(0,rtc.error_id());
 plc::output(0,rtc.done());plc::output(1,rtc.error());}
''', [F()], {"words":[0],"bits":[0,1]}, [E([256],[0,1])],
      "Generic pp164-165: simultaneous RD/WR is error256. No wall clock success is fabricated."),
]


def arithmetic_stress_case():
    # The oracle is integer mathematics and bit extraction, never m200.numeric,
    # SDK output, a compiler-generated expectation, or a second queue model.
    import random

    rng = random.Random(0x20061106)
    pairs = [(0,0),(32767,1),(32768,1),(65535,255),(65534,2),(1,255),(32767,255),(32768,255)]
    pairs += [(rng.randrange(65536),rng.randrange(256)) for _ in range(248)]
    frames, expected = [], []
    for raw, b in pairs:
        a = raw if raw < 32768 else raw - 65536
        values = [a+b,a-b,a*b]
        words = [v & 65535 for v in values] + [raw & b,raw | b,raw ^ b,(~raw)&65535,(raw<<1)&65535,raw>>1]
        bits = [not -32768 <= v <= 32767 for v in values] + [bool(raw & 32768),bool(raw & 1)]
        inputs = {n:bool(raw&(1<<n)) for n in range(16)}
        inputs.update({16+n:bool(b&(1<<n)) for n in range(8)})
        frames.append(F(inputs,0));expected.append(E(words,bits))
    return C("G02_seeded_256_alu_and_carry_boundaries", ["G02"],
        ["integer.add","integer.subtract","integer.multiply","word.and","word.or","word.xor","word.not","bits.shl","bits.shr"],r'''
void scan(){plc::i16 a=plc::read_input_bits_i16(0,16);plc::i16 b=plc::read_input_bits_i16(16,8);
 plc::clear_arithmetic_error();plc::write_word(0,plc::add_i16(a,b));plc::output(0,plc::system(18));
 plc::clear_arithmetic_error();plc::write_word(1,plc::sub_i16(a,b));plc::output(1,plc::system(18));
 plc::clear_arithmetic_error();plc::write_word(2,plc::mul_i16(a,b));plc::output(2,plc::system(18));
 plc::write_word(3,plc::and_i16(a,b));plc::write_word(4,plc::or_i16(a,b));
 plc::write_word(5,plc::xor_i16(a,b));plc::write_word(6,plc::not_i16(a));
 plc::write_word(7,plc::shl_i16(a,1));plc::output(3,plc::system(17));
 plc::write_word(8,plc::shr_i16(a,1));plc::output(4,plc::system(17));}
''',frames,{"words":list(range(9)),"bits":list(range(5))},expected,
        "Independent signed integer mathematics/raw bit extraction; seed0x20061106, eight fixed boundary pairs plus248 deterministic random pairs.")


def all_source_cases():
    return CASES + [arithmetic_stress_case()]
