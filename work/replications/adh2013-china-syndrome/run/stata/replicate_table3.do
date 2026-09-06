version 16.0
clear all
set more off
capture log close

args input outdir
if `"`input'"' == "" local input "work/replications/adh2013-china-syndrome/original/Autor-Dorn-Hanson-ChinaSyndrome-FileArchive/dta/workfile_china.dta"
if `"`outdir'"' == "" local outdir "work/replications/adh2013-china-syndrome/run/stata"

log using "`outdir'/replicate_table3.log", replace text
use "`input'", clear

local c1 "t2"
local c2 "l_shind_manuf_cbp t2"
local c3 "l_shind_manuf_cbp reg* t2"
local c4 "l_shind_manuf_cbp reg* l_sh_popedu_c l_sh_popfborn l_sh_empl_f t2"
local c5 "l_shind_manuf_cbp reg* l_sh_routine33 l_task_outsource t2"
local c6 "l_shind_manuf_cbp reg* l_sh_popedu_c l_sh_popfborn l_sh_empl_f l_sh_routine33 l_task_outsource t2"

tempname results
postfile `results' int specification double coefficient standard_error observations r_squared first_stage_coefficient first_stage_standard_error first_stage_F using "`outdir'/table3_results.dta", replace

forvalues j = 1/6 {
    local controls "`c`j''"

    quietly regress d_tradeusch_pw d_tradeotch_pw_lag `controls' [aw=timepwt48], cluster(statefip)
    local fs_b = _b[d_tradeotch_pw_lag]
    local fs_se = _se[d_tradeotch_pw_lag]
    quietly test d_tradeotch_pw_lag
    local fs_F = r(F)

    quietly ivregress 2sls d_sh_empl_mfg (d_tradeusch_pw = d_tradeotch_pw_lag) `controls' [aw=timepwt48], cluster(statefip)
    post `results' (`j') (_b[d_tradeusch_pw]) (_se[d_tradeusch_pw]) (e(N)) (e(r2)) (`fs_b') (`fs_se') (`fs_F')
}

postclose `results'
use "`outdir'/table3_results.dta", clear
format coefficient standard_error first_stage_coefficient first_stage_standard_error %12.9f
export delimited using "`outdir'/table3_results.csv", replace
save "`outdir'/table3_results.dta", replace

file open marker using "`outdir'/STATA_COMPLETE.txt", write replace text
file write marker "complete" _n
file close marker
log close
exit, clear
