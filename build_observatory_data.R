#!/usr/bin/env Rscript
# Observatory data layer: merge the 4 measures + Tsinghua relations for the 12 great powers,
# aggregated at DAILY, WEEKLY, MONTHLY resolutions. Empty period (0 articles) => 0 for the
# three implicit-threat indices. Outputs small CSVs the Streamlit app reads.
suppressPackageStartupMessages({library(data.table); library(jsonlite)})
OUT <- "/Users/siuwong/Desktop/Book Project Data/observatory try June 2026"; setwd(OUT)
EXT <- "/Users/siuwong/Desktop/Book Project Data/all classified text data three methods may 2026/implicit threat extension measure june 2026"
LEX <- "/Users/siuwong/Desktop/Book Project Data/implicit threat lexicon and LSS"

cat("[1] load measures ...\n")
ds <- rbindlist(lapply(readLines(file.path(EXT,"threat_ms_summary_book.jsonl")), function(l){
  r<-fromJSON(l); data.table(row_id=as.integer(r$row_id),
    deepseek=if(is.numeric(r$sentiment)&&length(r$sentiment)==1) r$sentiment else NA_real_)}))[!is.na(deepseek)]
ll <- fread(file.path(LEX,"implicit_threat_lex_lss_article.csv"),
            select=c("row_id","it_pct","it_lss"), encoding="UTF-8")
setnames(ll, c("it_pct","it_lss"), c("lexicon","lss"))
meta <- fread(file.path(EXT,"../foreign_affairs_iv.csv"),
              select=c("row_id","date","main_foreign_actors","sentiment"), encoding="UTF-8", showProgress=FALSE)
setnames(meta, "sentiment", "negativity")

a <- merge(meta[nchar(as.character(date))==10], ll, by="row_id", all.x=TRUE)
a <- merge(a, ds, by="row_id", all.x=TRUE)

grp <- list(US="United States", Russia=c("Soviet Union","Russia"), Japan="Japan",
  UK=c("United Kingdom","Britain","England"), France="France", India="India",
  Germany=c("Germany","West Germany","East Germany"),
  Vietnam=c("Vietnam","North Vietnam","South Vietnam"), `South Korea`="South Korea",
  Australia="Australia", Indonesia="Indonesia", Pakistan="Pakistan")
lab2c <- unlist(lapply(names(grp), function(c) setNames(rep(c,length(grp[[c]])), grp[[c]])))
long <- a[, .(actor=trimws(unlist(strsplit(as.character(main_foreign_actors),";")))),
          by=.(row_id,date,deepseek,lexicon,lss,negativity)][actor %in% names(lab2c)]
long[, `:=`(country=lab2c[actor], date=as.IDate(date))]

# --- append newly-scored backfill articles (People's Daily 2025-12 → 2026-06-12) ---
NEW <- "/Users/siuwong/Desktop/Book Project Data/People's Daily 2025-12 to June 12/scored_articles.csv"
if (file.exists(NEW)) {
  sc <- fread(NEW, encoding="UTF-8")[!is.na(date) & nchar(as.character(date))==10]
  setnames(sc, c("it_deepseek","it_lex","it_lss","sentiment"),
               c("deepseek","lexicon","lss","negativity"), skip_absent=TRUE)
  ln <- sc[, .(actor=trimws(unlist(strsplit(as.character(main_foreign_actors),";")))),
            by=.(date,deepseek,lexicon,lss,negativity)][actor %in% names(lab2c)]
  ln[, `:=`(row_id=NA_integer_, country=lab2c[actor], date=as.IDate(date))]
  long <- rbind(long, ln, fill=TRUE)
  cat(sprintf("[append] +%s new great-power article-rows from backfill (to %s)\n",
              format(nrow(ln),big.mark=","), as.character(max(ln$date))))
}

rel <- fread(file.path(EXT,"tsinghua_relations_long.csv"))[, .(country, ym, relations=score)]

measures <- c("deepseek","lexicon","lss","negativity")
aggregate_res <- function(period_expr, label){
  L <- copy(long); L[, period := period_expr(date)]
  obs <- L[, c(.(n_art=.N), lapply(.SD, function(x) mean(x, na.rm=TRUE))), by=.(country,period), .SDcols=measures]
  grid <- CJ(country=names(grp), period=seq(min(L$period), max(L$period), by=label))
  d <- merge(grid, obs, by=c("country","period"), all.x=TRUE)
  for (m in measures) d[is.na(get(m)), (m):=0]            # empty period => 0
  d[is.na(n_art), n_art:=0L]
  d[, ym := format(as.IDate(period),"%Y-%m")]
  d <- merge(d, rel, by=c("country","ym"), all.x=TRUE)     # attach monthly relations
  setorder(d, country, period); d[, ym:=NULL]
  d
}
mon_start  <- function(x) as.IDate(format(x,"%Y-%m-01"))
week_start <- function(x) x - (as.integer(format(x,"%u"))-1)   # Monday

cat("[2] aggregate daily / weekly / monthly ...\n")
fwrite(aggregate_res(function(x) x,          "day"),   "scores_daily.csv",   bom=TRUE)
fwrite(aggregate_res(week_start,             "week"),  "scores_weekly.csv",  bom=TRUE)
fwrite(aggregate_res(mon_start,              "month"), "scores_monthly.csv", bom=TRUE)
for(f in c("scores_daily.csv","scores_weekly.csv","scores_monthly.csv"))
  cat(sprintf("    %-20s %s rows\n", f, format(nrow(fread(f)),big.mark=",")))
cat("done\n")
