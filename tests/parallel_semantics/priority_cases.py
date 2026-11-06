"""Natal-priority composition and finite pending-host contracts, not executed."""

from .contracts import Case, frame as F, observation as E, source_case as C


CASES = [
    C("G02_direct_inc_dec_alias_boundaries_and_sticky_flag", ["G02"], ["integer.inc","integer.dec"], r'''
void scan(){plc::clear_arithmetic_error();plc::write_word(0,32767);plc::inc_word(0);
 plc::output(0,plc::system(18));plc::clear_arithmetic_error();plc::dec_word(0);
 plc::output(1,plc::system(18));plc::clear_arithmetic_error();plc::write_dword(2,-2147483648);
 plc::dec_dword(2);plc::output(2,plc::system(18));plc::write_word(4,plc::inc_i16(0));
 plc::write_dword(6,plc::dec_i32(0));plc::output(3,plc::system(18));}
''', [F()], {"words":[0,2,3,4,6,7],"bits":[0,1,2,3]}, [E([32767,65535,32767,1,65535,65535],[1,1,1,1])],
      "G02 inc/dec direct/typed contract plus explicit local modular overflow; valid expression calls do not clear prior S18."),
    C("G06_leaf_loop_early_return_resumes_master", ["G06"], ["control.subroutine"], r'''
void leaf(){plc::write_word(0,0);plc::i16 i=0;
 while(i<4){plc::write_word(0,plc::add_i16(plc::read_word(0),i));
  if(plc::input(0)&&i==2){return;}i=plc::add_i16(i,1);}
 plc::write_word(1,55);}
plc::Subroutine worker{63,leaf,"loop leaf",9};
void scan(){plc::write_word(1,99);worker.call(true);plc::write_word(2,30);}
''', [F({0:0}),F({0:1}),F({0:0})], {"words":[0,1,2]}, [E([6,55,30]),E([3,99,30]),E([6,55,30])],
      "G06 synchronous local return scope. Master suffix must run after both ordinary and early leaf returns."),
    C("G07_retention_and_dynamic_preset_are_separate_states", ["G07"], ["fb.tm","fb.timer_retention","fb.timer_dynamic_preset"], r'''
plc::Ton retained{0,10,3,true,false};plc::Ton dynamic{1,10,5,false,true};
void scan(){if(plc::input(2)){dynamic.set_preset(1);}
 bool a=retained.update(plc::input(0));bool b=dynamic.update(plc::input(1));
 plc::write_word(0,retained.value());plc::write_word(1,dynamic.value());
 plc::output(0,a);plc::output(1,b);}
''', [F({0:1,1:1},20),F({1:1,2:1},10),F({0:1,1:1},10),F({0:1,1:1},10),F({},0)],
      {"words":[0,1],"bits":[0,1]}, [E([0,0],[0,0]),E([2,2],[0,0]),E([2,2],[0,1]),E([3,2],[1,1]),E([0,0],[0,0])],
      "Existing TIMER-MODES local policy: retained pause, next-tick dynamic completion without clamping V, independent instances."),
    C("G07_execute_void_skipped_call_does_not_force_IN_false", ["G07"], ["fb.tm"], r'''
plc::Ton timer{0,10,2};
void scan(){if(plc::input(0)){timer.execute(plc::input(1));}
 plc::output(0,timer.done());plc::write_word(0,timer.value());}
''', [F({0:1,1:1},20),F({},10),F({},10),F({0:1},0)], {"words":[0],"bits":[0]},
      [E([0],[0]),E([2],[1]),E([2],[1]),E([0],[0])],
      "G07 execute-void contract; property reads observe elapsed enabled state while the call site is skipped."),
    C("G08_two_counters_circular_domain_and_repeated_pulses", ["G08"], ["fb.c"], r'''
plc::Counter boundary{0,9999};plc::Counter repeated{254,2};
void scan(){boundary.update(plc::input(0),plc::input(1),plc::input(2),plc::input(3));
 plc::i16 i=0;while(i<2){repeated.count_up(false);repeated.count_up(true);i=plc::add_i16(i,1);}
 plc::write_word(0,boundary.value());plc::write_word(1,repeated.value());
 plc::output(0,boundary.empty());plc::output(1,boundary.done());plc::output(2,boundary.full());}
''', [F(v) for v in [{},{1:1},{2:1},{2:1},{3:1}]], {"words":[0,1],"bits":[0,1,2]},
      [E([0,2],[0,0,0]),E([9999,4],[0,1,0]),E([0,6],[0,0,1]),E([0,8],[0,0,1]),E([9999,10],[1,1,1])],
      "Explicit COUNTERS.md local policy: 0..9999 wrap, per-pin edges and opposite-direction flag retention remain unqualified native behavior."),
    C("G11_first_TRUE_and_missing_transport_never_invent_success", ["G11"], ["comm.read_var","HW.COMM_READ_VAR"], r'''
plc::ReadVar read{0,plc::Link::Serial1,1,5,plc::Object::HoldingWords,0,1,100};
void scan(){if(plc::system(13)){plc::write_word(100,4321);}
 bool done=read.update(plc::input(0),false);plc::output(0,done);plc::output(1,read.busy());plc::output(2,read.error());
 plc::write_word(0,read.comm_error());plc::write_dword(1,read.oper_error());}
''', [F({0:v}) for v in [1,1,0,1,1,0]], {"words":[0,1,2,100],"bits":[0,1,2]},
      [E([0,0,0,4321],[0,0,0]),E([0,0,0,4321],[0,0,0]),E([0,0,0,4321],[0,0,0]),E([255,15,0,4321],[0,0,1]),E([255,15,0,4321],[0,0,1]),E([0,0,0,4321],[0,0,0])],
      "Generic communication edge/255-15 failure contract. No default peer/hook is installed and data words retain their sentinel."),
    C("G09_absolute_100ms_counter_rolls_low_word_at_32768", ["G09"], ["clock.absolute_counter","HW.RTC_SYSTEM_WORDS"], r'''
void scan(){plc::write_word(0,plc::read_system_word(18));plc::write_word(1,plc::read_system_word(19));}
''', [F({},3276700),F({},100),F({},100),F({},0)], {"words":[0,1]},
      [E([0,0]),E([32767,0]),E([0,1]),E([1,1])],
      "M200 Programming Guide SW18/SW19: 100ms, low word0..32767 then high increments; this is not a generic binary65536 split."),
]


PENDING_CASES = [
    Case("G01_external_word_bank_alias_and_live_input_order", ("G01",), ("bool.ld","bool.st"), "G01_external_images",
         "G01 contract requires explicit external image provider; no BooleanWord declaration creates hardware.",
         {"scenario":"word_bank_bit15_alias", "initial_words":{"%IW1.0":32768,"%QW1.0":1,"%IWS1.0":65535,"%QWS1.0":32767,"%SW114":32768,"%MW0":32768,"%KW0":32768},
          "reads":[15,0], "mutations":[{"bank":"%MW0","bit":15,"value":False}]},
         {"initial_bit15_bit0":{"%IW1.0":[True,False],"%QW1.0":[False,True],"%IWS1.0":[True,True],"%QWS1.0":[False,True],"%SW114":[True,False],"%MW0":[True,False],"%KW0":[True,False]},"mutated_MW0_u16":0}),
    Case("G01_edge_cold_warm_stop_RUN_history_is_not_guessed", ("G01",), ("bool.ldr","bool.ldf","bool.expression_rising"), "G01_lifecycle",
         "Native lifecycle equivalence remains pending. CONTRACT/DELIVERY must state the exact local event policy before an oracle is admitted.",
         {"scenario":"edge_lifecycle", "events":["cold_restart","run_input_true","stop","input_false_true_while_stopped","warm_restart","run_input_true"]},
         None, oracle_status="pending_contract_or_native_oracle"),
    Case("G07_timer_power_outage_and_warm_resume_exclude_outage", ("G07",), ("fb.tm",), "G07_lifecycle",
         "G07 timer-only host event contract; outage time must not become enabled timer ticks.",
         {"scenario":"timer_only_lifecycle","timer":{"kind":"TON","index":0,"base_ms":10,"preset":3},
          "events":[{"scan":True},{"advance_ms":20},{"scan":True},{"event":"power_off"},{"advance_ms":1000},
                    {"event":"warm_restart"},{"event":"run"},{"scan":True},{"advance_ms":10},{"scan":True}]},
         [{"value":0,"done":False},{"value":2,"done":False},{"value":2,"done":False},{"value":3,"done":True}]),
    Case("G07_STOP_keeps_timer_progress_separate_from_scan_admission", ("G07",), ("fb.tm",), "G07_lifecycle",
         "Generic pp109/113/117 explicitly says controller STOP does not freeze the value. Outage is a different event.",
         {"scenario":"timer_only_lifecycle","timer":{"kind":"TON","index":0,"base_ms":10,"preset":3},
          "events":[{"scan":True},{"advance_ms":20},{"probe":True},{"event":"stop"},{"advance_ms":1000},{"probe":True},{"event":"run"},{"scan":True}]},
         [{"value":0,"done":False},{"value":2,"done":False},{"value":3,"done":True},{"value":3,"done":True}]),
    Case("G07_timer_cold_restart_restores_configured_preset", ("G07",), ("fb.tm","fb.timer_dynamic_preset"), "G07_lifecycle",
         "G07 cold event contract restores configured P, not the latest runtime write.",
         {"scenario":"timer_only_cold","timer":{"kind":"TON","index":0,"base_ms":10,"preset":3,"dynamic":True},
          "events":[{"set_preset":7},{"scan":True},{"advance_ms":20},{"scan":True},{"event":"cold_restart"},{"event":"run"},{"scan":False}]},
         {"preset":3,"value":0,"done":False}),
    Case("G08_unresolved_native_domains_remain_visible_gaps", ("G08",), ("fb.sbr","fb.sc","fb.dr"), "G08_domains",
         "G08 explicitly retains unmodeled collision/endpoint domains; a refusal is not completed semantic coverage.",
         {"scenario":"unresolved_domains","requests":["SBR8001_left_fill","SBR_both_new_edges","SC255_increment","SC0_decrement","SC_multiple_true_bit_writes","DR_set_step_plus_advance"]},
         None, oracle_status="pending_native_oracle"),
    Case("G09_leap_calendar_and_century_rollover", ("G09",), ("HW.RTC","clock.snapshot"), "G09_clock",
         "Gregorian literal dates, separate explicit injected RTC image; elapsed scan time is not a system wall-clock source.",
         {"scenario":"calendar_rollovers","positions":[
             {"clock":"2000-02-28T23:59:59","advance_ms":1000},
             {"clock":"2100-02-28T23:59:59","advance_ms":1000},
             {"clock":"2026-12-31T23:59:59","advance_ms":1000}]},
         ["2000-02-29T00:00:00","2100-03-01T00:00:00","2027-01-01T00:00:00"]),
    Case("G09_invalid_staged_BCD_date_has_no_partial_commit", ("G09",), ("clock.set","HW.RTC_SYSTEM_WORDS"), "G09_clock",
         "G09 S50 transaction contract: validate complete staged calendar on falling S50; S52 marks invalid update.",
         {"scenario":"staged_clock_transaction","clock":"2026-01-31T23:59:59", "stage":{"year":2026,"month":2,"day":31,"hours":7,"minutes":8,"seconds":9},
          "before_commit_snapshot":True,"commit_on_S50_falling":True},
         {"before":"2026-01-31T23:59:59","after":"2026-01-31T23:59:59","S52":True}),
    Case("G09_schedule_OR_and_cold_enable_mask_need_DOW_binding", ("G09",), ("fb.schedule","HW.RTC_SCHEDULE"), "G09_schedule",
         "Generic EIO0000003289.04 p160 establishes same-output OR and SW114 cold maskFFFF. Vendor static ConversionHelper.ScheduleBlockDaysOfTheWeekMaskBuilder establishes Monday bit0/Tuesday bit1. Interior12:30 probes avoid boundary/wrap policy; cold hook is G09-family-only, not a full native lifecycle claim.",
         {"scenario":"two_schedules_shared_output","output":"%Q0.0","days":["Monday","Tuesday"],"start":"12:00","end":"13:00",
          "checks":["Monday12:30","Tuesday12:30","Wednesday12:30","both_disabled","cold_restart"],
          "indices":[0,15],
          "date_window":{"start_day":1,"start_month":1,"end_day":31,"end_month":12},
          "check_clocks":{"Monday12:30":"2026-11-09T12:30:00","Tuesday12:30":"2026-11-10T12:30:00",
                          "Wednesday12:30":"2026-11-11T12:30:00","both_disabled":"2026-11-10T12:30:00",
                          "cold_restart":"2026-11-10T12:30:00"}},
         [{"check":"Monday12:30","output":True,"SW114":65535},
          {"check":"Tuesday12:30","output":True,"SW114":65535},
          {"check":"Wednesday12:30","output":False,"SW114":65535},
          {"check":"both_disabled","output":False,"SW114":0},
          {"check":"cold_restart","output":True,"SW114":65535}]),
    Case("G11_busy_dynamic_buffer_change_does_not_redirect_active_read", ("G11",), ("comm.read_var","HW.COMM_READ_VAR"), "G11_async",
         "G11 Execute snapshots configuration. Test-owned scripted transport supplies literal bytes, never an implicit successful peer.",
         {"scenario":"busy_config_snapshot","config":{"kind":"READ_VAR","link":"SL1","id":1,"first_obj":0,"quantity":2,"index_data":100},
          "initial_words":{"100":1111,"101":2222,"200":3333,"201":4444},
          "events":[{"execute":False},{"execute":True,"transport_pending":True},{"set_property":{"IndexData":200},"execute":True,"transport_response_hex":"0304000B0016"}],
          "observe_request_pdu":True},
         {"request_hex":"0300000002","words":{"100":11,"101":22,"200":3333,"201":4444},"done":True,"error":False,"configured_index_data":200}),
    Case("G11_abort_prevents_late_response_buffer_mutation", ("G11",), ("comm.read_var",), "G11_async",
         "G11 abort cancels active work; a late scripted response must not overwrite application words.",
         {"scenario":"abort_late_response","config":{"kind":"READ_VAR","link":"SL1","id":1,"first_obj":0,"quantity":1,"index_data":100},
          "initial_words":{"100":12345},"events":[{"execute":False,"abort":False},{"execute":True,"transport_pending":True},
             {"execute":True,"abort":True},{"execute":True,"late_response_hex":"03020063"}]},
         {"words":{"100":12345},"aborted":True,"done":False}),
]
