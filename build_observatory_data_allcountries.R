#!/usr/bin/env Rscript
# C3 — Observatory data layer for ALL COUNTRIES + Taiwan. IDENTICAL method to
# build_observatory_data.R (same measures, same 0-filled grid, same conventions); the ONLY change
# is the country map: the 12 Tsinghua keys are kept verbatim (so they reproduce exactly) and every
# other sovereign country (+Taiwan) from C1's actor_to_country.csv is added. Weekly/monthly keep full
# history; the daily 0-filled grid is bounded to DAY_FROM to keep the file size sane (~219 countries).
suppressPackageStartupMessages({library(data.table); library(jsonlite)})
OUT <- "/Users/siuwong/Desktop/Book Project Data/observatory try June 2026"; setwd(OUT)
EXT <- "/Users/siuwong/Desktop/Book Project Data/all classified text data three methods may 2026/implicit threat extension measure june 2026"
LEX <- "/Users/siuwong/Desktop/Book Project Data/implicit threat lexicon and LSS"
MAP <- "/Users/siuwong/Desktop/Book Project Data/all classified text data three methods may 2026/all_countries_expansion/actor_to_country.csv"
DAY_FROM <- as.IDate("2016-01-01")   # daily grid lower bound (recent-monitoring era)

cat("[1] load measures ...\n")
ds <- rbindlist(lapply(readLines(file.path(EXT,"threat_ms_summary_book.jsonl")), function(l){
  r<-fromJSON(l); data.table(row_id=as.integer(r$row_id),
    deepseek=if(is.numeric(r$sentiment)&&length(r$sentiment)==1) r$sentiment else NA_real_)}))[!is.na(deepseek)]
ll <- fread(file.path(LEX,"implicit_threat_lex_lss_article.csv"),
            select=c("row_id","it_pct","it_lss"), encoding="UTF-8")
setnames(ll, c("it_pct","it_lss"), c("lexicon","lss"))
FRAMES <- c("law_deg","norms_deg","threat_deg","selfdef_deg","limited_deg","discr_deg")
meta <- fread(file.path(EXT,"../foreign_affairs_iv.csv"),
              select=c("row_id","date","main_foreign_actors","sentiment", FRAMES), encoding="UTF-8", showProgress=FALSE)
setnames(meta, "sentiment", "negativity")

a <- merge(meta[nchar(as.character(date))==10], ll, by="row_id", all.x=TRUE)
a <- merge(a, ds, by="row_id", all.x=TRUE)

# --- country map: 12 verbatim + all other countries (+Taiwan) from C1 ---
grp <- list(US="United States", Russia=c("Soviet Union","Russia"), Japan="Japan",
  UK=c("United Kingdom","Britain","England"), France="France", India="India",
  Germany=c("Germany","West Germany","East Germany"),
  Vietnam=c("Vietnam","North Vietnam","South Vietnam"), `South Korea`="South Korea",
  Australia="Australia", Indonesia="Indonesia", Pakistan="Pakistan")
ISO12 <- c("USA","RUS","JPN","GBR","FRA","IND","DEU","VNM","KOR","AUS","IDN","PAK")
m <- fread(MAP, encoding="UTF-8")[action=="map" & !(iso3 %in% ISO12)]
grp_new <- split(m$actor, m$country)                       # country name -> actor variants
grp <- c(grp, grp_new)
lab2c <- unlist(lapply(names(grp), function(c) setNames(rep(c,length(grp[[c]])), grp[[c]])))
cat(sprintf("    countries: %d (12 + %d new)\n", length(grp), length(grp_new)))

long <- a[, .(actor=trimws(unlist(strsplit(as.character(main_foreign_actors),";")))),
          by=c("row_id","date","deepseek","lexicon","lss","negativity",FRAMES)][actor %in% names(lab2c)]
long[, `:=`(country=lab2c[actor], date=as.IDate(date))]

# --- append newly-scored backfill articles (People's Daily 2025-12 -> 2026-06-12) ---
NEW <- "/Users/siuwong/Desktop/Book Project Data/People's Daily 2025-12 to June 12/scored_articles.csv"
if (file.exists(NEW)) {
  sc <- fread(NEW, encoding="UTF-8")[!is.na(date) & nchar(as.character(date))==10]
  setnames(sc, c("it_deepseek","it_lex","it_lss","sentiment"),
               c("deepseek","lexicon","lss","negativity"), skip_absent=TRUE)
  for (fr in FRAMES) if (!fr %in% names(sc)) sc[, (fr) := NA_real_]
  ln <- sc[, .(actor=trimws(unlist(strsplit(as.character(main_foreign_actors),";")))),
            by=c("date","deepseek","lexicon","lss","negativity",FRAMES)][actor %in% names(lab2c)]
  ln[, `:=`(row_id=NA_integer_, country=lab2c[actor], date=as.IDate(date))]
  long <- rbind(long, ln, fill=TRUE)
  cat(sprintf("[append] +%s new article-rows from backfill (to %s)\n",
              format(nrow(ln),big.mark=","), as.character(max(ln$date))))
}

rel <- fread(file.path(EXT,"tsinghua_relations_long.csv"))[, .(country, ym, relations=score)]
measures <- c("deepseek","lexicon","lss","negativity", FRAMES)

aggregate_res <- function(period_expr, label, day_from=NULL){
  L <- copy(long); L[, period := period_expr(date)]
  obs <- L[, c(.(n_art=.N), lapply(.SD, function(x) mean(x, na.rm=TRUE))), by=.(country,period), .SDcols=measures]
  lo <- if (is.null(day_from)) min(L$period) else max(min(L$period), day_from)
  grid <- CJ(country=names(grp), period=seq(lo, max(L$period), by=label))
  d <- merge(grid, obs, by=c("country","period"), all.x=TRUE)
  for (mz in measures) d[is.na(get(mz)), (mz):=0]          # empty period => 0
  d[is.na(n_art), n_art:=0L]
  d[, ym := format(as.IDate(period),"%Y-%m")]
  d <- merge(d, rel, by=c("country","ym"), all.x=TRUE)     # monthly relations (12 only; else NA)
  setorder(d, country, period); d[, ym:=NULL]
  d
}
mon_start  <- function(x) as.IDate(format(x,"%Y-%m-01"))
week_start <- function(x) x - (as.integer(format(x,"%u"))-1)   # Monday

cat("[2] aggregate daily / weekly / monthly ...\n")
fwrite(aggregate_res(function(x) x,  "day",   DAY_FROM), "scores_daily.csv",   bom=TRUE)
fwrite(aggregate_res(week_start,     "week"),            "scores_weekly.csv",  bom=TRUE)
fwrite(aggregate_res(mon_start,      "month"),           "scores_monthly.csv", bom=TRUE)
for(f in c("scores_daily.csv","scores_weekly.csv","scores_monthly.csv")){
  fi <- file.info(f); cat(sprintf("    %-20s %s rows  %.1f MB\n", f,
    format(nrow(fread(f)),big.mark=","), fi$size/1e6))
}
cat("done\n")
