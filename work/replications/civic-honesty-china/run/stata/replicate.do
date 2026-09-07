version 16
clear all
set more off
args experiment_file survey_file output_dir
capture mkdir "`output_dir'"

use "`experiment_file'", clear
snapshot save
local centered male age40 computer coworkers other_bystanders
foreach var of local centered {
    quietly summarize `var'
    generate dm_m_`var' = money * (`var' - r(mean))
}
local x1 male age40 computer coworkers other_bystanders
local x2 rice `x1' dm_m_male dm_m_age40 dm_m_computer dm_m_coworkers dm_m_other_bystanders

tempname table2
postfile `table2' str4 spec_id str24 outcome str12 term double estimate double std_error double p_value double nobs double df_resid using "`output_dir'/table2_results.dta", replace
local spec = 0
foreach outcome in email wallet_recovery wallet_totalrecovery {
    foreach controls in "" "`x1'" "`x2'" {
        local ++spec
        quietly regress `outcome' money `controls' i.city i.institution, robust
        local p = 2 * ttail(e(df_r), abs(_b[money] / _se[money]))
        post `table2' ("m`spec'") ("`outcome'") ("money") (_b[money]) (_se[money]) (`p') (e(N)) (e(df_r))
    }
}
postclose `table2'
use "`output_dir'/table2_results.dta", clear
format estimate std_error p_value %21.17g
format nobs df_resid %12.0g
export delimited using "`output_dir'/table2_results.csv", replace datafmt

use "`experiment_file'", clear
generate noemail_e = 100 * inlist(r_hnsty_nocontact, 4, 5, 6) if !missing(r_hnsty_nocontact)
generate takeaway_e = 100 * inlist(r_hnsty_takeaway, 4, 5, 6) if !missing(r_hnsty_takeaway)
graph bar noemail_e takeaway_e, ylabel(0(20)100) ytitle("Reporting rate (%)") name(field, replace)
graph export "`output_dir'/field-attitudes.png", replace width(1600)

use "`survey_file'", clear
replace noemail = 100 * noemail
replace takeaway = 100 * takeaway
graph bar noemail takeaway, ylabel(0(20)100) ytitle("Reporting rate (%)") name(survey, replace)
graph export "`output_dir'/survey-attitudes.png", replace width(1600)

file open marker using "`output_dir'/STATA_COMPLETE.txt", write replace
file write marker "complete" _n
file close marker
exit, clear
