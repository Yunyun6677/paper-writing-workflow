version 16.0
clear all
set more off
args input outdir
if `"`input'"' == "" local input "../python/analysis.csv"
if `"`outdir'"' == "" local outdir "."
capture mkdir `"`outdir'"'
capture log close _all
log using `"`outdir'/execution.log"', text replace
import delimited using `"`input'"', clear varnames(1) asdouble
keep if analysis_sample == 1
tempname handle
postfile `handle' str4 spec_id str8 term double estimate double std_error double n double df_resid using `"`outdir'/table4_results.dta"', replace
quietly regress demp nj
post `handle' ("m1") ("nj") (_b[nj]) (_se[nj]) (e(N)) (e(df_r))
quietly regress demp nj bk kfc roys co_owned
post `handle' ("m2") ("nj") (_b[nj]) (_se[nj]) (e(N)) (e(df_r))
quietly regress demp gap
post `handle' ("m3") ("gap") (_b[gap]) (_se[gap]) (e(N)) (e(df_r))
quietly regress demp gap bk kfc roys co_owned
post `handle' ("m4") ("gap") (_b[gap]) (_se[gap]) (e(N)) (e(df_r))
quietly regress demp gap bk kfc roys centralj southj pa1 pa2
post `handle' ("m5") ("gap") (_b[gap]) (_se[gap]) (e(N)) (e(df_r))
postclose `handle'
use `"`outdir'/table4_results.dta"', clear
format estimate std_error %24.17g
export delimited using `"`outdir'/table4_results.csv"', replace datafmt
file open done using `"`outdir'/STATA_COMPLETE.txt"', write text replace
file write done "complete" _n
file close done
log close
exit, clear
