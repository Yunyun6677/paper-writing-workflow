args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 5) stop("Expected input CSV, SVG, PNG, session info, and completion marker")

input <- args[[1]]
figure <- args[[2]]
preview <- args[[3]]
session_file <- args[[4]]
marker <- args[[5]]
data <- read.csv(input, check.names = FALSE, stringsAsFactors = FALSE)
required <- c("term", "estimate", "std_error")
if (!all(required %in% names(data))) stop("Missing required coefficient columns")
if (nrow(data) == 0 || any(!is.finite(data$estimate)) || any(!is.finite(data$std_error)) || any(data$std_error < 0)) {
  stop("Invalid coefficient values")
}

labels <- if ("spec_id" %in% names(data)) paste(data$spec_id, data$term, sep = ": ") else data$term
ordering <- order(data$estimate)
data <- data[ordering, , drop = FALSE]
labels <- labels[ordering]
lower <- data$estimate - 1.96 * data$std_error
upper <- data$estimate + 1.96 * data$std_error
height <- max(4.5, 0.34 * nrow(data) + 1.8)

draw_plot <- function() {
  par(mar = c(4.5, max(7, min(18, max(nchar(labels)) * 0.45)), 2, 1))
  y <- seq_len(nrow(data))
  plot(data$estimate, y, xlim = range(c(lower, upper, 0)), yaxt = "n", pch = 19,
       xlab = "Estimate with 95% confidence interval", ylab = "", main = "Coefficient plot")
  segments(lower, y, upper, y, col = "#2166ac", lwd = 2)
  points(data$estimate, y, pch = 19, col = "#b2182b")
  abline(v = 0, lty = 2, col = "grey45")
  axis(2, at = y, labels = labels, las = 1, cex.axis = 0.8)
  box()
}

svg(figure, width = 9, height = height)
draw_plot()
dev.off()
png(preview, width = 1440, height = max(720, round(height * 160)), res = 160)
draw_plot()
dev.off()

writeLines(capture.output(sessionInfo()), session_file)
writeLines("complete", marker)
