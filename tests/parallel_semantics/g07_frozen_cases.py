"""Additional independent G07 vectors for natal-G07-integration-1 only.

Literal arithmetic follows Generic107-118 and the explicitly labelled local
activation/tick/history policy. No production timer helper computes a want.
"""

from .contracts import Case, frame as F, observation as E, source_case as C


CASES = [
    C("G07_repeated_sites_execute_in_source_order_same_timestamp",["G07"],["fb.tm"],r'''
plc::Ton timer{0,10,2};
void scan(){bool first=timer.update(plc::input(0));
 if(plc::input(1)){timer.execute(false);}timer.execute(plc::input(2));
 plc::write_word(0,timer.value());plc::output(0,first);plc::output(1,timer.done());}
''',[F({0:1,2:1},20),F({0:1,1:1,2:1},20),F({0:1,2:1},0),F({2:1},0),F({0:1},0)],
      {"words":[0],"bits":[0,1]},[E([0],[0,0]),E([0],[1,0]),E([2],[1,1]),E([0],[0,0]),E([0],[0,0])],
      "Repeated update/execute calls share one identity and one timestamp; explicit false between true calls resets TON immediately."),
    C("G07_loop_repetition_is_not_another_tick_or_activation",["G07"],["fb.tm"],r'''
plc::Ton timer{0,10,2};
void scan(){plc::i16 n=0;while(n<4){timer.execute(true);n=plc::add_i16(n,1);}
 plc::write_word(0,timer.value());plc::output(0,timer.done());}
''',[F({},10),F({},10),F({},0)],{"words":[0],"bits":[0]},[E([0],[0]),E([1],[0]),E([2],[1])],
      "Elapsed timestamps0,10,20ms; four calls in each scan must not reset or multiply progress."),
    C("G07_internal_Q_completes_while_skipped_wired_coil_holds",["G07"],["fb.tm"],r'''
plc::Ton timer{0,10,2};
void scan(){if(plc::input(0)){bool wired=timer.update(plc::input(1));plc::output(0,wired);}
 plc::output(1,timer.done());plc::write_word(0,timer.value());}
''',[F({0:1,1:1},20),F({},10),F({},10),F({0:1},0)],{"words":[0],"bits":[0,1]},
      [E([0],[0,0]),E([2],[0,1]),E([2],[0,1]),E([0],[0,0])],
      "Generic109 skipped timer does not freeze; the omitted output instruction retains its image while public Q changes."),
    C("G07_zero_preset_distinguishes_TON_TOF_TP",["G07"],["fb.tm"],r'''
plc::Ton on{0,10,0};plc::Tof off{1,10,0};plc::Pulse pulse{2,10,0};
void scan(){bool a=on.update(plc::input(0));bool b=off.update(plc::input(0));bool c=pulse.update(plc::input(0));
 plc::output(0,a);plc::output(1,b);plc::output(2,c);}
''',[F({0:v},10) for v in [0,1,1,0,1]],{"bits":[0,1,2]},
      [E(bits=r) for r in [(0,0,0),(1,1,0),(1,1,0),(0,0,0),(1,1,0)]],
      "Allowed P0 boundary, ordinary per-call local policy; no physical zero-duration pulse is claimed."),
    C("G07_sparse_last_ID_minute_and_maximum_fast_preset",["G07"],["fb.tm"],r'''
plc::Ton minute{254,60000,1};plc::Ton fast{5,1,9999};
void scan(){bool a=minute.update(true);bool b=fast.update(true);plc::output(0,a);plc::output(1,b);
 plc::write_word(0,minute.value());plc::write_word(1,fast.value());}
''',[F({},9998),F({},1),F({},50000),F({},1),F({},0)],{"words":[0,1],"bits":[0,1]},
      [E([0,0],[0,0]),E([0,9998],[0,0]),E([0,9999],[0,1]),E([0,9999],[0,1]),E([1,9999],[1,1])],
      "Generic bases/P bounds and target ID limits: timestamps0,9998,9999,59999,60000ms, TM5 is last1ms-capable ID."),
    C("G07_dynamic_growth_does_not_resurrect_completed_activation",["G07"],["fb.timer_dynamic_preset"],r'''
plc::Ton timer{0,10,2,false,true};
void scan(){if(plc::input(1)){timer.set_preset(5);}bool done=timer.update(plc::input(0));plc::output(0,done);
 plc::write_word(0,timer.preset());plc::write_word(1,timer.value());}
''',[F({0:1},20),F({0:1},0),F({0:1,1:1},30),F({0:1},0),F({},0),F({0:1},50),F({0:1},0)],
      {"words":[0,1],"bits":[0]},[E([2,0],[0]),E([2,2],[1]),E([5,2],[1]),E([5,2],[1]),E([5,0],[0]),E([5,0],[0]),E([5,5],[1])],
      "Explicit TIMER-MODES completed-activation policy, separately qualified from documentary dynamic behavior."),
    C("G07_nondynamic_preset_write_waits_for_next_activation",["G07"],["fb.tm"],r'''
plc::Ton timer{0,10,5};
void scan(){if(plc::input(1)){timer.set_preset(1);}bool done=timer.update(plc::input(0));plc::output(0,done);
 plc::write_word(0,timer.preset());plc::write_word(1,timer.value());}
''',[F({0:1},20),F({0:1,1:1},10),F({0:1},20),F({0:1},0),F({},0),F({0:1},10),F({0:1},0)],
      {"words":[0,1],"bits":[0]},[E([5,0],[0]),E([1,2],[0]),E([1,3],[0]),E([1,5],[1]),E([1,0],[0]),E([1,0],[0]),E([1,1],[1])],
      "Ordinary preset captures at activation; writing P while active does not enable dynamic mode."),
    C("G07_retained_dynamic_TON_paused_equality_then_smaller",["G07"],["fb.timer_retention","fb.timer_dynamic_preset"],r'''
plc::Ton timer{0,100,5,true,true};
void scan(){if(plc::input(1)){timer.set_preset(2);}if(plc::input(2)){timer.set_preset(1);}
 bool done=timer.update(plc::input(0));plc::output(0,done);plc::write_word(0,timer.preset());plc::write_word(1,timer.value());}
''',[F({0:1},250),F({},0),F({1:1},0),F({2:1},0),F({0:1},100),F({0:1},0)],
      {"words":[0,1],"bits":[0]},[E([5,0],[0]),E([5,2],[0]),E([2,2],[0]),E([1,0],[0]),E([1,0],[0]),E([1,1],[1])],
      "Generic retentive/dynamic diagrams and local strict-less-than pause rule; P==V must retain V, smaller P resets V."),
    C("G07_retained_dynamic_TOF_mirrors_pause_level",["G07"],["fb.timer_retention","fb.timer_dynamic_preset"],r'''
plc::Tof timer{0,100,5,true,true};
void scan(){if(plc::input(1)){timer.set_preset(2);}if(plc::input(2)){timer.set_preset(1);}
 bool done=timer.update(plc::input(0));plc::output(0,done);plc::write_word(0,timer.preset());plc::write_word(1,timer.value());}
''',[F({0:1},100),F({},250),F({0:1},0),F({0:1,1:1},0),F({0:1,2:1},0),F({},100),F({},0)],
      {"words":[0,1],"bits":[0]},[E([5,0],[1]),E([5,0],[1]),E([5,2],[1]),E([2,2],[1]),E([1,0],[1]),E([1,0],[1]),E([1,1],[0])],
      "TOF pauses on INtrue, unlike TON. Equality/smaller-P and next falling activation are literal mirror controls."),
    C("G07_active_TP_ignores_new_edge_and_held_TRUE_after_completion",["G07"],["fb.tm"],r'''
plc::Pulse timer{0,100,3};
void scan(){bool done=timer.update(plc::input(0));plc::output(0,done);plc::write_word(0,timer.value());}
''',[F({0:v},100) for v in [1,0,1,1,1,0,1]],{"words":[0],"bits":[0]},
      [E([0],[1]),E([1],[1]),E([2],[1]),E([3],[0]),E([3],[0]),E([0],[0]),E([0],[1])],
      "Generic TP diagram: no extension by new edge while pulse active. Inactive V reset on false is the labelled local policy."),
]


HOST_CASES = [
    Case("G07_TON_outage_preserves_fractional_phase",("G07",),("fb.tm",),"G07_lifecycle",
         "Generic warm/outage preservation, with explicit existing local phase: elapsed150ms then outage does not consume the remaining50ms.",
         {"scenario":"timer_only_lifecycle","timer":{"kind":"TON","index":0,"base_ms":100,"preset":3},
          "events":[{"scan":True},{"advance_ms":150},{"probe":True},{"event":"power_off"},{"advance_ms":1000},{"probe":True},
                    {"event":"warm_restart"},{"advance_ms":49},{"probe":True},{"advance_ms":1},{"probe":True},{"advance_ms":100},{"probe":True}]},
         [{"value":0,"done":False},{"value":1,"done":False},{"value":1,"done":False},{"value":1,"done":False},{"value":2,"done":False},{"value":3,"done":True}]),
    Case("G07_TOF_outage_preserves_delay_not_IN_edge",("G07",),("fb.tm",),"G07_lifecycle",
         "TOF delay starts at falling IN; warm resume preserves active delay and its local fractional phase.",
         {"scenario":"timer_only_lifecycle","timer":{"kind":"TOF","index":0,"base_ms":100,"preset":3},
          "events":[{"scan":True},{"advance_ms":100},{"scan":False},{"advance_ms":150},{"probe":True},{"event":"power_off"},{"advance_ms":1000},{"probe":True},
                    {"event":"warm_restart"},{"advance_ms":49},{"probe":True},{"advance_ms":1},{"probe":True},{"advance_ms":100},{"probe":True}]},
         [{"value":0,"done":True},{"value":0,"done":True},{"value":1,"done":True},{"value":1,"done":True},{"value":1,"done":True},{"value":2,"done":True},{"value":3,"done":False}]),
    Case("G07_TP_outage_does_not_complete_unpowered_pulse",("G07",),("fb.tm",),"G07_lifecycle",
         "TP active pulse is paused by outage, not by false IN; getters during outage must not advance it.",
         {"scenario":"timer_only_lifecycle","timer":{"kind":"TP","index":0,"base_ms":100,"preset":3},
          "events":[{"scan":True},{"advance_ms":150},{"probe":True},{"event":"power_off"},{"advance_ms":1000},{"probe":True},
                    {"event":"warm_restart"},{"advance_ms":49},{"probe":True},{"advance_ms":1},{"probe":True},{"advance_ms":100},{"probe":True}]},
         [{"value":0,"done":True},{"value":1,"done":True},{"value":1,"done":True},{"value":1,"done":True},{"value":2,"done":True},{"value":3,"done":False}]),
    Case("G07_TOF_STOP_does_not_freeze_falling_delay",("G07",),("fb.tm",),"G07_lifecycle",
         "Generic113 STOP does not freeze TOF; no new falling edge is required to finish an already active delay.",
         {"scenario":"timer_only_lifecycle","timer":{"kind":"TOF","index":0,"base_ms":100,"preset":3},
          "events":[{"scan":True},{"advance_ms":100},{"scan":False},{"advance_ms":150},{"probe":True},{"event":"stop"},{"advance_ms":300},{"probe":True},{"event":"run"},{"scan":False}]},
         [{"value":0,"done":True},{"value":0,"done":True},{"value":1,"done":True},{"value":3,"done":False},{"value":3,"done":False}]),
    Case("G07_TP_STOP_and_RUN_do_not_retrigger_held_input",("G07",),("fb.tm",),"G07_lifecycle",
         "Generic117 STOP does not freeze TP. RUN with the existing true input is not a fresh call-history edge.",
         {"scenario":"timer_only_lifecycle","timer":{"kind":"TP","index":0,"base_ms":100,"preset":3},
          "events":[{"scan":True},{"advance_ms":150},{"probe":True},{"event":"stop"},{"advance_ms":300},{"probe":True},{"event":"run"},{"scan":True}]},
         [{"value":0,"done":True},{"value":1,"done":True},{"value":3,"done":False},{"value":3,"done":False}]),
    Case("G07_TOF_cold_restart_clears_Q_and_restores_config_P",("G07",),("fb.tm",),"G07_lifecycle",
         "Generic113 cold reset explicitly sets V/Q0 and configured P; first false after cold is not an invented falling edge.",
         {"scenario":"timer_only_cold","timer":{"kind":"TOF","index":0,"base_ms":100,"preset":5},
          "events":[{"scan":True},{"set_preset":7},{"event":"cold_restart"},{"event":"run"},{"scan":False}]},
         {"preset":5,"value":0,"done":False}),
    Case("G07_TP_cold_restart_clears_active_pulse_and_config_P",("G07",),("fb.tm",),"G07_lifecycle",
         "Generic117 cold reset clears V/Q and restores configured P; this does not certify CPU RAM/fallback lifecycle.",
         {"scenario":"timer_only_cold","timer":{"kind":"TP","index":0,"base_ms":100,"preset":5},
          "events":[{"scan":True},{"advance_ms":150},{"set_preset":7},{"event":"cold_restart"},{"event":"run"},{"scan":False}]},
         {"preset":5,"value":0,"done":False}),
]


BOUND_CASE = Case("G07_constructor_identity_base_preset_boundaries",("G07",),("fb.tm","fb.timer_retention"),"G07_bounds",
    "Generic/target identity and numeric domains; positive controls bracket every constructor rejection and both backends execute real constructors.",
    {"probes":[
        {"name":"id0_preset0","declarations":"plc::Ton a{0,1,0};"},
        {"name":"last_fast_id5","declarations":"plc::Ton a{5,1,9999};"},
        {"name":"last_id_minute","declarations":"plc::Tof a{254,60000,9999};"},
        {"name":"combined_TON","declarations":"plc::Ton a{0,10,2,true,true};"},
        {"name":"combined_TOF","declarations":"plc::Tof a{0,100,2,true,true};"},
        {"name":"dynamic_TP","declarations":"plc::Pulse a{0,100,2,false,true};"},
        {"name":"id255","declarations":"plc::Ton a{255,100,2};"},
        {"name":"id_negative","declarations":"plc::Ton a{-1,100,2};"},
        {"name":"base1_id6","declarations":"plc::Ton a{6,1,2};"},
        {"name":"invalid_base2","declarations":"plc::Ton a{0,2,2};"},
        {"name":"negative_preset","declarations":"plc::Ton a{0,100,-1};"},
        {"name":"preset10000","declarations":"plc::Ton a{0,100,10000};"},
        {"name":"retentive_TP","declarations":"plc::Pulse a{0,100,2,true,false};"},
        {"name":"shared_identity_duplicate","declarations":"plc::Ton a{0,100,2};plc::Tof b{0,100,2};"}
    ]},
    [{"name":name,"accepted":accepted} for name,accepted in [
        ("id0_preset0",True),("last_fast_id5",True),("last_id_minute",True),("combined_TON",True),("combined_TOF",True),("dynamic_TP",True),
        ("id255",False),("id_negative",False),("base1_id6",False),("invalid_base2",False),("negative_preset",False),("preset10000",False),("retentive_TP",False),("shared_identity_duplicate",False)
    ]])


def stress_cases():
    # This is a literal period table, not a reimplementation of TimerState.
    # Repeated t0 calls and the base-1/base boundary are included every period.
    phases = [0,0,0,1,2,3,4,5,6,7]
    words = [(0,0,0),(1,0,1),(2,0,2),(3,0,2),(0,0,0),(0,1,0),(0,2,0),(0,3,0)]
    bits = [(0,1,1),(0,1,1),(0,1,0),(1,1,0),(0,1,0),(0,1,0),(0,1,0),(0,0,0)]
    result = []
    for base in [1,10,100,1000,60000]:
        deltas = [0,base-1,1,base,base,base,base,base,base,base]
        frames = [F({0:phase<4},delta) for _ in range(64) for phase,delta in zip(phases,deltas)]
        expected = [E(words[phase],bits[phase]) for _ in range(64) for phase in phases]
        body = f'''
plc::Ton on{{0,{base},3}};plc::Tof off{{1,{base},3}};plc::Pulse pulse{{2,{base},2}};
void scan(){{bool a=on.update(plc::input(0));bool b=off.update(plc::input(0));bool c=pulse.update(plc::input(0));
 plc::write_word(0,on.value());plc::write_word(1,off.value());plc::write_word(2,pulse.value());
 plc::output(0,a);plc::output(1,b);plc::output(2,c);}}
'''
        result.append(C("G07_stress_640_frames_three_modes_base_"+str(base),["G07"],["fb.tm"],body,frames,
                        {"words":[0,1,2],"bits":[0,1,2]},expected,
                        "Independent eight-phase literal table,64periods/640frames. Boundaries0,base-1,base and repeated timestamps; base="+str(base)+"ms."))
    return result
