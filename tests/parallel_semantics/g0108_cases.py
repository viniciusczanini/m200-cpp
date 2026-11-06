"""G01/G08 independent source literals and native questions, freeze3.

Authorities: Generic Functions .04 pp37-48,82-83,147-158; M200 .06
pp22-26,321-340. Runtime lifecycle/endpoint ambiguities stay PENDING.
"""
from .contracts import Case, source_case as C, frame as F, observation as E

CASES = []
PENDING = []

CASES.append(C("G01_new_shared_KW_SW17_RTC_word_bit_images", ["G01"], ["bool.ld", "bool.st"], r'''
plc::ConstantMemory constants{512};plc::ConstantDword pair{510,-2147483647};plc::ConstantWord high{511,-32768};
void scan(){plc::write_word(0,4660);plc::write_bit("%MW0:X15",true);plc::write_system_word(17,5);
 bool old=plc::read_bit("%SW17:X2");plc::reset_bit("%SW17:X2",true);plc::set_bit("%SW17:X15",false);
 plc::write_word(1,plc::read_system_word(17));plc::write_bit("%S50",true);plc::write_bit("%SW53:X3",true);plc::reset_bit("%S50",true);
 plc::write_word(2,plc::read_system_word(53));plc::write_bit("%M1023",true);plc::reset_bit("%M1023",false);plc::set_bit("%M0",false);
 plc::output(0,plc::read_bit("%KW511:X15"));plc::output(1,plc::read_bit("%KW510:X0"));plc::output(2,old);
 plc::output(3,plc::read_bit("%MW0:X15"));plc::output(4,plc::read_bit("%M1023"));plc::output(5,plc::read_bit("%M0"));
 plc::output(6,plc::read_bit("%S52"));plc::output(7,plc::read_bit("%S51"));}
''', [F({}, 0)], {"words": [0, 1, 2], "bits": list(range(8))},
    [E([0x9234, 1, 0x2008], [1, 1, 1, 1, 1, 0, 0, 0])],
    "One G02 KW/KD image, one SW17 status and one RTC staged year. Bit15 and false S/R preserve aliases and unrelated bits. S50 commit is local; no native snapshot atomicity assertion."))

CASES.append(C("G01_new_stack_snapshot_last_MW_and_input_alias", ["G01"], ["stack.mps"], r'''
plc::WordMemory words{8000};
void scan(){plc::BooleanStack s;plc::write_word(7999,-32768);s.push(plc::read_bit("%MW7999:X15"));
 plc::write_word(7999,0);plc::output(0,s.peek());plc::output(1,s.pop());plc::output(2,plc::read_bit("%MW7999:X15"));}
''', [F({}, 0)], {"words": [7999], "bits": [0, 1, 2]}, [E([0], [1, 1, 0])],
    "Snapshot value survives overwrite at MW7999; no implicit MW8000 scratch cell is available."))

push = ["s.push(plc::input(0));" if i % 2 == 0 else "s.push(!plc::input(0));" for i in range(32)]
pop = ["plc::output(" + str(i % 16) + ",s.pop());" for i in range(32)]
CASES.append(C("G01_new_stack_exact_32_values_LIFO", ["G01"], ["stack.mps", "stack.mpp"],
    "void scan(){plc::BooleanStack s;" + "".join(push + pop) + "}",
    [F({0: 0}, 0), F({0: 1}, 0)], {"bits": list(range(16))},
    [E(bits=[1, 0] * 8), E(bits=[0, 1] * 8)],
    "Documented local 32-expression capacity; opposite alternating literals expose LIFO order and snapshot reuse."))

CASES.append(C("G01_new_stack_balanced_branch_and_loop", ["G01"], ["stack.mps", "stack.mpp"], r'''
void scan(){plc::BooleanStack s;plc::write_word(0,0);if(plc::input(0)){s.push(true);plc::output(0,s.pop());}else{s.push(false);plc::output(0,s.pop());}
 plc::i16 i=0;while(i<4){s.push(plc::input(0));if(s.pop()){plc::inc_word(0);}i=plc::add_i16(i,1);}}
''', [F({0: 0}, 0), F({0: 1}, 0)], {"words": [0], "bits": [0]}, [E([0], [0]), E([4], [1])],
    "Local restricted C++ balancing at each branch and loop iteration; skipped branches do not retain stack entries."))

full_m = "plc::BitMemory image{1024};void scan(){" + "".join("plc::write_m(" + str(i) + "," + ("plc::input(0)" if i % 2 == 0 else "!plc::input(0)") + ");" for i in range(1024)) + "plc::output(0,plc::read_m(0));plc::output(1,plc::read_m(1023));}"
CASES.append(C("G01_new_full_1024_M_assignment_domain", ["G01"], ["bool.st"], full_m,
    [F({0: 0}, 0), F({0: 1}, 0)], {"bits": [0, 1]}, [E(bits=[0, 1]), E(bits=[1, 0])],
    "M200 Boolean capacity1024. Every M identity is explicitly assigned; boundary observations must survive compiler liveness without unrequested private M."))

CASES.append(Case("G01_new_explicit_master_sample_and_nonmaster_expression_history", ("G01",), ("bool.ldr",), "G0108_cycles",
    "Local MAST sample is stable across repeated task bodies; writes after sample affect next master boundary. Expression history updates per executed call, not per master boundary. First-false history is local policy.",
    {"source": r'''#include <plc.hpp>
plc::BooleanContext context{true,true};
void scan(){bool a=plc::input_rising(0);bool b=plc::input_rising(0);bool m=plc::m_rising(100);bool e=plc::rising(0,plc::input(0));
 plc::write_m(100,plc::input(1));plc::output(0,a);plc::output(1,b);plc::output(2,m);plc::output(3,e);plc::output(4,plc::input(0));plc::output(5,plc::input_falling(0));plc::output(6,plc::m_falling(100));}
''', "bits": list(range(7)), "events": [
        {"master": {}}, {"scan": {}}, {"master": {0: 1, 1: 1}}, {"scan": {0: 1, 1: 1}}, {"scan": {0: 1, 1: 1}},
        {"master": {0: 0, 1: 1}}, {"scan": {0: 0, 1: 1}}, {"scan": {0: 1, 1: 0}}, {"master": {0: 1, 1: 0}}, {"scan": {0: 1, 1: 0}}]},
    [{"bits": b} for b in [[0, 0, 0, 0, 0, 0, 0], [1, 1, 0, 1, 1, 0, 0], [1, 1, 0, 0, 1, 0, 0],
                           [0, 0, 1, 0, 0, 1, 0], [0, 0, 1, 1, 1, 1, 0], [1, 1, 0, 0, 1, 0, 1]]]))

CASES.append(Case("G01_new_nonmaster_does_not_reapply_RTC_schedule", ("G01", "G09"), ("bool.st",), "G0108_cycles",
    "One master boundary applies the existing RTC schedule; non-master bodies must not reapply it. This composes the new sampling API with already-tested schedule policy.",
    {"source": '#include <plc.hpp>\nplc::Schedule s{0,1,0,1,1,12,0,31,12,13,0,127};\nvoid scan(){if(plc::input(0)){plc::output(0,false);}plc::output(1,plc::output_state(0));}',
     "clock": [2026, 11, 9, 12, 30, 0], "bits": [0, 1], "events": [{"master": {}}, {"scan": {0: 1}}, {"scan": {}}, {"master": {}}, {"scan": {}}]},
    [{"bits": [0, 0]}, {"bits": [0, 0]}, {"bits": [1, 1]}]))

CASES.append(Case("G01_new_S13_is_first_master_cycle_not_first_task_body", ("G01",), ("bool.ld",), "G0108_cycles",
    "Coordinator-confirmed explicit host contract: non-master calls retain the current first-cycle flag; opening the second master boundary ends the previous first cycle in VM and SDK. Not a claim about unobserved physical warm/cold lifecycle.",
    {"source": '#include <plc.hpp>\nvoid scan(){plc::output(0,plc::system(13));}', "bits": [0],
     "events": [{"master": {}}, {"scan": {}}, {"scan": {}}, {"master": {}}, {"scan": {}}, {"scan": {}}, {"master": {}}, {"scan": {}}]},
    [{"bits": [v]} for v in [1, 1, 0, 0, 0]]))

CASES.append(Case("G01_new_live_input_snapshots_cross_external_callback", ("G01",), ("bool.ld",), "G0108_external",
    "Live-I context materializes values at evaluation points. Explicit external S66 callback changes I0.0 between reads; no scheduler or physical I/O is invented.",
    {"source": '#include <plc.hpp>\nplc::BooleanContext context{false,false};void scan(){bool before=plc::input(0);bool trigger=plc::read_bit("%S66");bool after=plc::input(0);plc::output(0,before);plc::output(1,trigger);plc::output(2,after);}',
     "flip_input": True, "frames": [{0: 0}, {0: 1}], "bits": [0, 1, 2]},
    [{"bits": [0, 1, 1], "external_words": []}, {"bits": [1, 1, 0], "external_words": []}]))

CASES.append(Case("G01_new_external_word_status_banks_RMW", ("G01",), ("bool.ld", "bool.st"), "G0108_external",
    "Each external value/status identity is explicit. QW word-bit write performs owning-word RMW, preserving every other bit; status/IW objects remain read-only.",
    {"source": r'''#include <plc.hpp>
plc::BooleanWord a{"%IW1.0"};plc::BooleanWord b{"%QW1.0"};plc::BooleanWord c{"%IWS1.0"};plc::BooleanWord d{"%QWS1.0"};
void scan(){plc::output(0,plc::read_bit("%IW1.0:X15"));plc::output(1,plc::read_bit("%QW1.0:X0"));plc::output(2,plc::read_bit("%IWS1.0:X15"));plc::output(3,plc::read_bit("%QWS1.0:X15"));
 plc::write_bit("%QW1.0:X15",true);plc::reset_bit("%QW1.0:X0",true);plc::output(4,plc::read_bit("%QW1.0:X15"));plc::output(5,plc::read_bit("%QW1.0:X0"));}
''', "external_words": {"%IW1.0": 32768, "%QW1.0": 1, "%IWS1.0": 65535, "%QWS1.0": 32767}, "frames": [{}], "bits": list(range(6))},
    [{"bits": [1, 1, 1, 0, 1, 0], "external_words": [32768, 32768, 65535, 32767]}]))

CASES.append(C("G08_new_SBR_endpoint_bits_are_discarded_on_safe_vacated_zero", ["G08"], ["fb.sbr"], r'''
plc::ShiftBitRegister up{7};plc::ShiftBitRegister down{0};
void scan(){if(plc::system(13)){up.set_bit(15,true);down.set_bit(0,true);}up.update(false,plc::input(0),false);down.update(false,false,plc::input(0));
 plc::output(0,up.bit(15));plc::output(1,up.bit(0));plc::output(2,down.bit(0));plc::output(3,down.bit(15));}
''', [F({}, 0), F({0: 1}, 0), F({0: 1}, 0), F({}, 0)], {"bits": [0, 1, 2, 3]},
    [E(bits=b) for b in [[1, 0, 1, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]],
    "Generic pp153-155 shifts discard outgoing bit. Vacated endpoint starts zero, avoiding unresolved fill with a set vacated endpoint."))

frames, expected = [F({}, 0)], [E(bits=[1, 0, 0, 0, 0])]
for active in range(1, 256):
    row = E(bits=[active == n for n in [0, 1, 127, 254, 255]])
    frames += [F({0: 1}, 0), F({}, 0)]
    expected += [row, row]
CASES.append(C("G08_new_SC_all_256_steps_without_endpoint_wrap", ["G08"], ["fb.sc"], r'''
plc::StepCounter step{7};void scan(){step.update(false,plc::input(0),false);plc::output(0,step.bit(0));plc::output(1,step.bit(1));plc::output(2,step.bit(127));plc::output(3,step.bit(254));plc::output(4,step.bit(255));}
''', frames, {"bits": list(range(5))}, expected,
    "Generic pp155-158 one-hot steps0..255; exactly255 fresh CU requests reach255. No CU at255 or CD at0 is assigned a guessed outcome."))

cams = ["plc::DrumCam{" + str(i) + ",plc::DrumOutput::Memory," + str(i) + "," + str(1 << i) + "}" for i in range(8)]
cams += ["plc::DrumCam{" + str(8+i) + ",plc::DrumOutput::Output," + str(8+i) + "," + str(255 ^ (1 << i)) + "}" for i in range(8)]
body = "plc::Drum drum{7,8," + ",".join(cams) + "};void scan(){drum.update(false,plc::input(0));plc::write_word(0,drum.step());plc::output(0,drum.full());plc::output(1,plc::read_m(0));plc::output(2,plc::read_m(7));}"
frames, expected = [F({}, 0)], []
steps = [0]
for step in [1, 2, 3, 4, 5, 6, 7, 0]:
    frames += [F({0: 1}, 0), F({0: 1}, 0), F({}, 0)]
    steps += [step] * 3
for step in steps:
    expected.append(E([step], [step == 7, step == 0, step == 7] + [step != i for i in range(8)]))
CASES.append(C("G08_new_DR_eight_steps_sixteen_cams_distinct_M_Q", ["G08"], ["fb.dr"], body,
    frames, {"words": [0], "bits": [0, 1, 2] + list(range(8, 16))}, expected,
    "Generic pp147-151 native DR capacity8steps/16cam slots. Independent one-hot/inverse masks test every step, F at7, held U, wrap and distinct M/Q destinations. Initial cam application is labelled cold-construction local policy."))

CASES.append(C("G08_new_single_step_DR_without_reset_is_deterministic", ["G08"], ["fb.dr"], r'''
plc::Drum drum{0,1,plc::DrumCam{15,plc::DrumOutput::Memory,1023,255},plc::DrumCam{0,plc::DrumOutput::Output,15,0}};
void scan(){if(plc::input(1)){drum.update(false,plc::input(0));}plc::write_word(0,drum.step());plc::output(0,drum.full());plc::output(1,plc::read_m(1023));}
''', [F({}, 0), F({0: 1, 1: 1}, 0), F({1: 1}, 0)], {"words": [0], "bits": [0, 1, 15]},
    [E([0], [1, 1, 0])] * 3,
    "Local construction applies cams even before first call. One configured step stays0 with F true for ordinary U; reset in this configuration is deliberately PENDING native."))

CASES.append(C("G08_new_shared_leaf_SR_observes_intermediate_sequence_state", ["G08", "G06"], ["fb.sbr", "fb.sc", "fb.dr", "control.subroutine"], r'''
plc::ShiftBitRegister sbr{7};plc::StepCounter sc{6};plc::Drum dr{5,3,plc::DrumCam{15,plc::DrumOutput::Memory,1023,2}};
void leaf(){sbr.update(false,false,false);sc.update(false,false,false);dr.update(false,false);sbr.update(false,true,false);sc.update(false,true,false);dr.update(false,true);}
plc::Subroutine action{0,leaf,"Sequences",2};
void scan(){if(plc::system(13)){sbr.set_bit(14,true);}action.call(true);plc::output(0,sbr.bit(15));plc::output(1,sc.bit(1));plc::write_word(0,dr.step());plc::output(2,plc::read_m(1023));
 action.call(true);plc::output(3,sbr.bit(15));plc::output(4,sc.bit(2));plc::write_word(1,dr.step());plc::output(5,dr.full());plc::output(6,plc::read_m(1023));}
''', [F({}, 0)], {"words": [0, 1], "bits": list(range(7))}, [E([1, 2], [1, 1, 1, 0, 1, 1, 0])],
    "One shared identity per family across repeated synchronous SR calls; native-style state snapshots before/after second call. Per-call first/cold history remains labelled local policy pending official lifecycle trials."))


def bounds_case(name, probes, engines=("vm", "sdk")):
    CASES.append(Case(name, ("G01", "G08"), ("bounds",), "G0108_bounds", "M200/documented SDK domains; true invalid identities/permissions, not unresolved native transitions.",
                      {"probes": [{"name": n, "source": s} for n, s, _ in probes], "engines": list(engines)},
                      [{"name": n, "accepted": accepted} for n, _, accepted in probes]))


bounds_case("G01_new_closed_addresses_permissions_and_bit_domains", [
    ("word_bit15", 'void scan(){plc::write_bit("%MW7999:X15",true);}', True),
    ("word_bit16", 'void scan(){plc::write_bit("%MW0:X16",true);}', False),
    ("MW8000", 'void scan(){plc::write_bit("%MW8000:X0",true);}', False),
    ("M1024", 'void scan(){plc::write_bit("%M1024",true);}', False),
    ("noncanonical_M00", 'void scan(){plc::write_bit("%M00",true);}', False),
    ("KW_read511", 'plc::ConstantWord c{511,-32768};void scan(){plc::output(0,plc::read_bit("%KW511:X15"));}', True),
    ("KW_write", 'void scan(){plc::write_bit("%KW0:X0",true);}', False),
    ("KW512", 'void scan(){plc::output(0,plc::read_bit("%KW512:X0"));}', False),
    ("input_readonly", 'void scan(){plc::write_bit("%I0.0",true);}', False),
    ("S52_readonly", 'void scan(){plc::write_bit("%S52",true);}', False),
    ("SW49_readonly", 'void scan(){plc::write_bit("%SW49:X0",true);}', False),
    ("SW118_readonly", 'void scan(){plc::write_bit("%SW118:X0",true);}', False),
    ("S18_reset_only", 'void scan(){plc::set_bit("%S18",true);}', False),
    ("S18_reset", 'void scan(){plc::reset_bit("%S18",true);}', True),
    ("unbound_S66", 'void scan(){plc::output(0,plc::read_bit("%S66"));}', False),
    ("unbound_IW", 'plc::BooleanWord a{"%IW1.0"};void scan(){plc::output(0,plc::read_bit("%IW1.0:X0"));}', False),
    ("IWS_readonly", 'plc::BooleanWord a{"%IWS1.0"};void scan(){plc::write_bit("%IWS1.0:X0",true);}', False),
    ("QWS_readonly", 'plc::BooleanWord a{"%QWS1.0"};void scan(){plc::write_bit("%QWS1.0:X0",true);}', False),
])
bounds_case("G01_new_stack_capacity_underflow_guards", [
    ("push33", "void scan(){plc::BooleanStack s;" + "s.push(false);" * 33 + "}", False),
    ("pop_empty", "void scan(){plc::BooleanStack s;plc::output(0,s.pop());}", False),
    ("peek_empty", "void scan(){plc::BooleanStack s;plc::output(0,s.peek());}", False),
])
bounds_case("G01_new_stack_source_balance_context_guards", [
    ("open_at_return", "void scan(){plc::BooleanStack s;s.push(true);return;}", False),
    ("conditional_pop", "void scan(){plc::BooleanStack s;s.push(true);if(plc::input(0)){plc::output(0,s.pop());}}", False),
    ("open_loop", "void scan(){plc::BooleanStack s;plc::i16 i=0;while(i<2){s.push(true);i=plc::add_i16(i,1);}}", False),
], engines=("vm",))

probes = []
for kind in ("ShiftBitRegister", "StepCounter"):
    probes += [(kind + "_ID7", "plc::" + kind + " a{7};void scan(){}", True),
               (kind + "_ID8", "plc::" + kind + " a{8};void scan(){}", False),
               (kind + "_duplicate", "plc::" + kind + " a{0};plc::" + kind + " b{0};void scan(){}", False)]
    last = 15 if kind == "ShiftBitRegister" else 255
    probes += [(kind + "_bit_last", "plc::" + kind + " a{0};void scan(){plc::output(0,a.bit(" + str(last) + "));}", True),
               (kind + "_bit_past", "plc::" + kind + " a{0};void scan(){plc::output(0,a.bit(" + str(last + 1) + "));}", False)]
probes += [("separate_same_ID_pools", "plc::ShiftBitRegister a{7};plc::StepCounter b{7};plc::Drum c{7,8};void scan(){}", True),
           ("DR_ID8", "plc::Drum a{8,8};void scan(){}", False), ("DR_steps0", "plc::Drum a{0,0};void scan(){}", False),
           ("DR_steps9", "plc::Drum a{0,9};void scan(){}", False), ("DR_duplicate", "plc::Drum a{0,8};plc::Drum b{0,8};void scan(){}", False),
           ("cam_slot15_M1023_mask255", "plc::Drum a{0,8,plc::DrumCam{15,plc::DrumOutput::Memory,1023,255}};void scan(){}", True),
           ("cam_slot16", "plc::Drum a{0,8,plc::DrumCam{16,plc::DrumOutput::Memory,0,1}};void scan(){}", False),
           ("cam_mask256", "plc::Drum a{0,8,plc::DrumCam{0,plc::DrumOutput::Memory,0,256}};void scan(){}", False),
           ("cam_M1024", "plc::Drum a{0,8,plc::DrumCam{0,plc::DrumOutput::Memory,1024,1}};void scan(){}", False),
           ("cam_Q16", "plc::Drum a{0,8,plc::DrumCam{0,plc::DrumOutput::Output,16,1}};void scan(){}", False),
           ("DR_step8", "plc::Drum a{0,8};void scan(){a.set_step(8);}", False)]
bounds_case("G08_new_documented_identity_bit_cam_boundaries", probes)

partial = 'void scan(){plc::div_word(0,7,0);plc::clear_arithmetic_error();plc::write_bit("%MW0:X0",true);'
bounds_case("G01_new_string_word_bits_preserve_partial_taint_guards", [
    ("written_bit_is_known", partial + 'plc::output(0,plc::read_bit("%MW0:X0"));}', True),
    ("other_bit_stays_unknown", partial + 'plc::output(0,plc::read_bit("%MW0:X1"));}', False),
    ("whole_word_stays_unknown", partial + 'plc::write_word(1,plc::read_word(0));}', False),
    ("full_bit_repair_is_known", partial + ''.join('plc::write_bit("%MW0:X' + str(i) + '",false);' for i in range(1,16)) + 'plc::write_word(1,plc::read_word(0));}', True),
])
bounds_case("G08_new_negative_identity_duplicate_cam_and_pin_mask_guards", [
    ("SBR_negative_ID", 'plc::ShiftBitRegister a{-1};void scan(){}', False),
    ("SC_negative_ID", 'plc::StepCounter a{-1};void scan(){}', False),
    ("DR_negative_ID", 'plc::Drum a{-1,8};void scan(){}', False),
    ("DR_duplicate_cam_slot", 'plc::Drum a{0,8,plc::DrumCam{0,plc::DrumOutput::Memory,1,1},plc::DrumCam{0,plc::DrumOutput::Memory,2,2}};void scan(){}', False),
    ("DR_negative_cam_mask", 'plc::Drum a{0,8,plc::DrumCam{0,plc::DrumOutput::Memory,1,-1}};void scan(){}', False),
    ("DR_negative_cam_address", 'plc::Drum a{0,8,plc::DrumCam{0,plc::DrumOutput::Memory,-1,1}};void scan(){}', False),
    ("SBR_mask0", 'plc::ShiftBitRegister a{0};void scan(){a.update_pins(0,false,false,false);}', False),
    ("SBR_mask8", 'plc::ShiftBitRegister a{0};void scan(){a.update_pins(8,false,false,false);}', False),
    ("DR_mask0", 'plc::Drum a{0,8};void scan(){a.update_pins(0,false,false);}', False),
    ("DR_mask4", 'plc::Drum a{0,8};void scan(){a.update_pins(4,false,false);}', False),
    ("SBR_only_CU_present_inactive", 'plc::ShiftBitRegister a{0};void scan(){a.update_pins(2,false,false,false);}', True),
    ("DR_only_U_present_inactive", 'plc::Drum a{0,8};void scan(){a.update_pins(2,false,false);}', True),
])

repair_source = 'void scan(){plc::write_system_word(17,5);plc::div_word(0,7,0);plc::write_bit("%MW0:X0",true);bool first=plc::read_bit("%MW0:X0");'
repair_source += ''.join('plc::write_bit("%MW0:X' + str(i) + '",false);' for i in range(1,16))
repair_source += 'plc::write_word(1,plc::read_word(0));plc::write_word(2,plc::read_system_word(17));plc::output(0,first);plc::output(1,plc::read_bit("%MW0:X15"));plc::output(2,plc::system(18));}'
CASES.append(C("G01_new_string_bit_repairs_restore_exact_word_keep_other_flags", ["G01", "G02"], ["bool.st", "integer.divide"], repair_source,
    [F({}, 0)], {"words": [0, 1, 2], "bits": [0, 1, 2]}, [E([1, 1, 5], [1, 0, 1])],
    "Exact literal payload after all16 string-address writes repair an unknown word; S18 stays set and independent SW17 stays5. No unspecified value is inspected before full repair."))

copy_repair = 'void scan(){plc::div_word(0,7,0);plc::write_bit("%MW0:X0",true);plc::copy_word(1,0);'
copy_repair += ''.join('plc::write_bit("%MW0:X' + str(i) + '",false);' for i in range(1,16))
copy_source = copy_repair + 'bool copied=plc::read_bit("%MW1:X0");'
copy_source += ''.join('plc::write_bit("%MW1:X' + str(i) + '",false);' for i in range(1,16))
copy_source += 'plc::output(0,copied);plc::output(1,plc::system(18));}'
CASES.append(C("G01_new_explicit_copy_word_partial_mask_then_independent_full_repairs", ["G01", "G02"], ["bool.st", "assign.scalar"], copy_source,
    [F({}, 0)], {"words": [0, 1], "bits": [0, 1]}, [E([1, 1], [1, 1])],
    "G02 supported explicit copy API preserves known bit0 and unknown masks without inspecting unspecified payload. Both actual images are repaired independently before whole-word observations; S18 stays set."))
bounds_case("G01_new_explicit_copy_keeps_unknown_mask_after_source_repair", [
    ("copied_other_bit_still_unknown", copy_repair + 'plc::output(0,plc::read_bit("%MW1:X1"));}', False),
])

# These cannot acquire expected success traces until native evidence resolves
# their outcomes. Sources and observations are ready for the final vendor batch.
for name, source, observation, question in [
    ("SBR_set_vacated_endpoint", 'plc::ShiftBitRegister a{0};void scan(){a.set_bit(0,true);a.update(false,true,false);}', ["%SBR0.0..15"], "After CU with old bit0=1, is vacated bit0 zero, retained or transferred?"),
    ("SBR_two_fresh_directions", 'plc::ShiftBitRegister a{0};void scan(){a.set_bit(4,true);a.update(false,true,true);}', ["%SBR0.0..15"], "Collision priority/no-op and histories after both pins are held/released separately."),
    ("SBR_reset_with_held_history", 'plc::ShiftBitRegister a{0};void scan(){a.update(false,true,false);a.update(true,false,false);}', ["%SBR0.0..15"], "Does exclusive reset clear prior CU history, and what happens after held CU?"),
    ("SC_CD_at_zero", 'plc::StepCounter a{0};void scan(){a.update(false,false,true);}', ["%SC0.0", "%SC0.255"], "Wrap, saturation, invalid/empty state or other native endpoint behavior?"),
    ("SC_CU_at_255", 'plc::StepCounter a{0};void scan(){for(plc::i16 i=0;i<256;i=plc::add_i16(i,1)){a.update(false,false,false);a.update(false,true,false);}}', ["%SC0.0", "%SC0.255"], "256th fresh CU endpoint and subsequent opposite request."),
    ("SC_active_changing_write", 'plc::StepCounter a{0};void scan(){a.set_bit(7,true);}', ["%SC0.0", "%SC0.7"], "Does write select a step, permit multiple true bits or reject at firmware runtime?"),
    ("DR_pending_step_plus_fresh_U", 'plc::Drum a{0,3};void scan(){a.set_step(2);a.update(false,true);}', ["%DR0.S", "%DR0.F"], "Priority and visibility of pending literal step write against U edge."),
    ("DR_single_step_reset", 'plc::Drum a{0,1};void scan(){a.update(true,false);}', ["%DR0.S", "%DR0.F"], "F during reset for one configured step."),
    ("DR_aliased_cam_bindings", 'plc::Drum a{0,2,plc::DrumCam{0,plc::DrumOutput::Memory,100,1},plc::DrumCam{1,plc::DrumOutput::Memory,100,2}};void scan(){a.update(false,true);}', ["%DR0.S", "%M100"], "Column priority/OR/last-write across conflicting same-output cams."),
    ("omitted_active_direction_history", 'plc::ShiftBitRegister a{0};void scan(){a.update(false,true,false);a.update_pins(1,false,false,false);}', ["%SBR0.0..15"], "How omitted pin history changes after an earlier active pin."),
]:
    PENDING.append({"name": "G08_native_PENDING_" + name, "status": "PENDING_NATIVE_ORACLE", "source": "#include <plc.hpp>\n" + source,
                    "observe": observation, "question": question, "expected": None,
                    "classification": "Tool runtime gap; never a PLC impossibility or semantic PASS"})
PENDING.append({"name": "G01_native_PENDING_edge_lifecycle", "status": "PENDING_NATIVE_ORACLE", "expected": None,
                "source": '#include <plc.hpp>\nvoid scan(){plc::output(0,plc::input_rising(0));plc::output(1,plc::input_falling(0));plc::output(2,plc::rising(0,plc::input(0)));}',
                "observe": ["%I0.0", "%Q0.0..2", "RUN/STOP", "S0/S1"],
                "sequence": ["cold with I true", "RUN steady", "STOP", "I false/true while stopped", "warm RUN with I true", "first and second steady scan"],
                "question": "Initial/history reset and physical input sampling phase across actual controller lifecycle.",
                "classification": "Local per-call/sample policy is tested separately; native lifecycle remains unresolved"})
