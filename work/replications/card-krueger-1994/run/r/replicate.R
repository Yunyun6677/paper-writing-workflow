args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 2) stop("Expected analysis CSV and output directory")
input <- args[[1]]
output <- args[[2]]
dir.create(output, recursive = TRUE, showWarnings = FALSE)
data <- read.csv(input, stringsAsFactors = FALSE)
sample <- data[data$analysis_sample == 1, ]

specifications <- list(
  m1 = list(target = "nj", formula = demp ~ nj),
  m2 = list(target = "nj", formula = demp ~ nj + bk + kfc + roys + co_owned),
  m3 = list(target = "gap", formula = demp ~ gap),
  m4 = list(target = "gap", formula = demp ~ gap + bk + kfc + roys + co_owned),
  m5 = list(target = "gap", formula = demp ~ gap + bk + kfc + roys + centralj + southj + pa1 + pa2)
)

rows <- lapply(names(specifications), function(id) {
  specification <- specifications[[id]]
  fit <- lm(specification$formula, data = sample, na.action = na.omit)
  table <- summary(fit)$coefficients
  target <- specification$target
  data.frame(spec_id = id, term = target, estimate = table[target, "Estimate"],
             std_error = table[target, "Std. Error"], n = nobs(fit), df_resid = df.residual(fit))
})
results <- do.call(rbind, rows)
write.csv(results, file.path(output, "table4_results.csv"), row.names = FALSE)
writeLines(capture.output(sessionInfo()), file.path(output, "session-info.txt"))
writeLines("complete", file.path(output, "R_COMPLETE.txt"))
