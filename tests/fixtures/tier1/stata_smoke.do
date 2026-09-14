version 16.0
clear all
set more off
set obs 100
generate double x = _n
generate double y = 1 + 2*x
regress y x, vce(robust)
assert abs(_b[x]-2)<1e-10
clear
set obs 1
generate double coefficient = 2
export delimited using "result.csv", replace
exit, clear
