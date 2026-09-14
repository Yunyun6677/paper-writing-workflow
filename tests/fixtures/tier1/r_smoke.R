x <- seq_len(100)
y <- 1 + 2 * x
fit <- lm(y ~ x)
result <- data.frame(term = names(coef(fit)), estimate = unname(coef(fit)))
write.csv(result, "result.csv", row.names = FALSE)
if (abs(coef(fit)[["x"]] - 2) > 1e-10) stop("slope mismatch")
