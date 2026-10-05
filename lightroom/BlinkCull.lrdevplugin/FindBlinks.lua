-- Blink Cull for Lightroom Classic.
-- Takes the selected photos, hands them to the Blink Cull engine (a bundled command-line program) and writes
-- colour labels, keywords and collections straight into the catalog.
-- It never deletes or rejects photos and never modifies the RAW files.

local LrApplication = import "LrApplication"
local LrBinding = import "LrBinding"
local LrDialogs = import "LrDialogs"
local LrFileUtils = import "LrFileUtils"
local LrFunctionContext = import "LrFunctionContext"
local LrPathUtils = import "LrPathUtils"
local LrPrefs = import "LrPrefs"
local LrProgressScope = import "LrProgressScope"
local LrTasks = import "LrTasks"
local LrView = import "LrView"

local prefs = LrPrefs.prefsForPlugin()

-- ---------------------------------------------------------------- texts (English / Romanian)
local STRINGS = {
  en = {
    dialogTitle = "Blink Cull: closed eyes",
    analyze = "Analyze",
    selected = "%d selected photos will be analyzed (ARW files only).",
    language = "Language:",
    engine = "Engine:",
    red = "Red (closed) at score >=",
    yellow = "   Yellow (to check) at score >=",
    skipLabeled = "Leave photos that already have a colour label alone",
    addKeywords = "Add keywords (blinkcull-closed / blinkcull-check)",
    makeCollections = "Create collections with the photos found (easy to review in the grid)",
    noPhotos = "No photo is selected. Select photos (or a folder) and run again.",
    noEngine = "The Blink Cull engine was not found at:\n%s\n\nReinstall the plugin (the engine lives in its bin folder) or enter the correct path in the dialog.",
    noArw = "None of the selected photos is an ARW (Sony RAW) file. Only ARW is supported for now.",
    cannotWrite = "Cannot write the temporary file:\n%s",
    progress = "Blink Cull: analyzing photos",
    canceled = "Analysis canceled. Nothing was changed in the catalog.",
    engineFailed = "The engine did not finish (code %s).\nCheck the engine path and try again. Nothing was changed in the catalog.",
    undoName = "Blink Cull: labels",
    collRed = "Blink Cull %s - red (closed)",
    collYellow = "Blink Cull %s - yellow (to check)",
    doneTitle = "Blink Cull: done",
    analyzed = "Analyzed: %d ARW photos.",
    redLine = "Red (closed, score >= %.2f): %d",
    yellowLine = "Yellow (to check, score >= %.2f): %d",
    okLine = "No problem: %d  |  no judged face: %d",
    keptLine = "Kept with their existing label: %d",
    errLine = "Errors / missing files: %d",
    skipLine = "Ignored (not ARW): %d",
    labelFailed = "WARNING: could not set the colour label on %d photos (keywords and collections were applied).",
  },
  ro = {
    dialogTitle = "Blink Cull: ochi închiși",
    analyze = "Analizează",
    selected = "Se analizează %d poze selectate (doar fișiere ARW).",
    language = "Limba:",
    engine = "Motor:",
    red = "Roșu (închis) la scor >=",
    yellow = "   Galben (de verificat) la scor >=",
    skipLabeled = "Nu schimba pozele care au deja o etichetă de culoare",
    addKeywords = "Adaugă cuvinte cheie (blinkcull-closed / blinkcull-check)",
    makeCollections = "Creează colecții cu pozele găsite (ușor de parcurs în grilă)",
    noPhotos = "Nu e nicio poză selectată. Selectează pozele (sau un folder) și rulează din nou.",
    noEngine = "Nu găsesc motorul Blink Cull la:\n%s\n\nReinstalează plugin-ul (motorul e în folderul lui bin) sau completează calea corectă în dialog.",
    noArw = "Nicio poză selectată nu e în format ARW (Sony RAW). Momentan doar ARW e acceptat.",
    cannotWrite = "Nu pot scrie fișierul temporar:\n%s",
    progress = "Blink Cull: analizez pozele",
    canceled = "Analiza a fost anulată. Nu am modificat nimic în catalog.",
    engineFailed = "Motorul nu a terminat analiza (cod %s).\nVerifică calea motorului și încearcă din nou. Nu am modificat nimic în catalog.",
    undoName = "Blink Cull: etichete",
    collRed = "Blink Cull %s - roșii (închise)",
    collYellow = "Blink Cull %s - galbene (de verificat)",
    doneTitle = "Blink Cull: gata",
    analyzed = "Analizate: %d poze ARW.",
    redLine = "Roșii (închise, scor >= %.2f): %d",
    yellowLine = "Galbene (de verificat, scor >= %.2f): %d",
    okLine = "Fără probleme: %d  |  fără față judecată: %d",
    keptLine = "Păstrate cu eticheta lor existentă: %d",
    errLine = "Erori / fișiere lipsă: %d",
    skipLine = "Ignorate (nu sunt ARW): %d",
    labelFailed = "ATENȚIE: nu am putut seta eticheta de culoare la %d poze (cuvintele cheie și colecțiile au fost aplicate).",
  },
}

-- ---------------------------------------------------------------- helpers
local function q(s) return '"' .. s .. '"' end

local function run(cmd)
  if WIN_ENV then cmd = '"' .. cmd .. '"' end  -- cmd.exe wants one more pair of quotes around the whole command
  return LrTasks.execute(cmd)
end

local function readAll(path)
  local fh = io.open(path, "rb")
  if not fh then return nil end
  local s = fh:read("*a")
  fh:close()
  return s
end

local function exe(base) return WIN_ENV and (base .. ".exe") or base end

-- The engine ships inside the plugin folder (bin/BlinkCullEngine/). A path saved in the preferences is only used
-- when the bundled engine is missing (for example a developer build elsewhere).
local function defaultEngine()
  local bundled = LrPathUtils.child(LrPathUtils.child(LrPathUtils.child(_PLUGIN.path, "bin"), "BlinkCullEngine"), exe("BlinkCullEngine"))
  if LrFileUtils.exists(bundled) == "file" then return bundled end
  if prefs.engine and LrFileUtils.exists(prefs.engine) == "file" then return prefs.engine end
  local home = LrPathUtils.getStandardFilePath("home")
  local dev = home .. "/blink-cull/dist/BlinkCullEngine/BlinkCullEngine"
  if LrFileUtils.exists(dev) == "file" then return dev end
  return bundled
end

local function showDialog(context, count)
  local f = LrView.osFactory()
  local props = LrBinding.makePropertyTable(context)
  props.language = prefs.language or "en"
  props.engine = defaultEngine()
  props.closedMin = prefs.closedMin or 0.45
  props.checkMin = prefs.checkMin or 0.25
  props.skipLabeled = (prefs.skipLabeled ~= false)
  props.addKeywords = (prefs.addKeywords ~= false)
  props.makeCollections = (prefs.makeCollections ~= false)
  local S = STRINGS[props.language] or STRINGS.en

  local contents = f:column {
    bind_to_object = props,
    spacing = f:control_spacing(),
    f:static_text { title = string.format(S.selected, count) },
    f:row {
      f:static_text { title = S.language, width = 90 },
      f:popup_menu {
        value = LrView.bind("language"),
        items = { { title = "English", value = "en" }, { title = "Română", value = "ro" } },
      },
      f:static_text { title = "  (applies from the next run)" },
    },
    f:row {
      f:static_text { title = S.engine, width = 90 },
      f:edit_field { value = LrView.bind("engine"), width_in_chars = 55 },
    },
    f:row {
      f:static_text { title = S.red, width = 160 },
      f:edit_field { value = LrView.bind("closedMin"), width_in_chars = 5, precision = 2, min = 0, max = 1 },
      f:static_text { title = S.yellow },
      f:edit_field { value = LrView.bind("checkMin"), width_in_chars = 5, precision = 2, min = 0, max = 1 },
    },
    f:checkbox { title = S.skipLabeled, value = LrView.bind("skipLabeled") },
    f:checkbox { title = S.addKeywords, value = LrView.bind("addKeywords") },
    f:checkbox { title = S.makeCollections, value = LrView.bind("makeCollections") },
  }

  local result = LrDialogs.presentModalDialog {
    title = S.dialogTitle,
    contents = contents,
    actionVerb = S.analyze,
  }
  if result ~= "ok" then return nil end
  for _, k in ipairs { "language", "engine", "closedMin", "checkMin", "skipLabeled", "addKeywords", "makeCollections" } do
    prefs[k] = props[k]
  end
  return props
end

-- ---------------------------------------------------------------- main
LrFunctionContext.postAsyncTaskWithContext("BlinkCull", function(context)
  local catalog = LrApplication.activeCatalog()
  local photos = catalog:getTargetPhotos()
  local S0 = STRINGS[prefs.language or "en"] or STRINGS.en
  if #photos == 0 then
    LrDialogs.message("Blink Cull", S0.noPhotos, "info")
    return
  end

  local opt = showDialog(context, #photos)
  if not opt then return end
  local S = STRINGS[opt.language] or STRINGS.en
  local closedMin, checkMin = tonumber(opt.closedMin) or 0.45, tonumber(opt.checkMin) or 0.25
  if LrFileUtils.exists(opt.engine) ~= "file" then
    LrDialogs.message("Blink Cull", string.format(S.noEngine, tostring(opt.engine)), "critical")
    return
  end

  -- 1) the list of photos: path -> catalog photos using it (virtual copies share a path)
  local byPath, order, skippedFormat = {}, {}, 0
  for _, photo in ipairs(photos) do
    local path = photo:getRawMetadata("path")
    if path and path:lower():match("%.arw$") then
      if not byPath[path] then byPath[path] = {}; order[#order + 1] = path end
      table.insert(byPath[path], photo)
    else
      skippedFormat = skippedFormat + 1
    end
  end
  if #order == 0 then
    LrDialogs.message("Blink Cull", S.noArw, "info")
    return
  end

  local tmp = LrPathUtils.getStandardFilePath("temp")
  local listFile = LrPathUtils.child(tmp, "blinkcull_list.txt")
  local outFile = LrPathUtils.child(tmp, "blinkcull_out.tsv")
  local progFile = LrPathUtils.child(tmp, "blinkcull_progress.txt")
  local cancelFile = LrPathUtils.child(tmp, "blinkcull_cancel.flag")
  for _, p in ipairs { outFile, progFile, cancelFile } do LrFileUtils.delete(p) end

  local fh = io.open(listFile, "wb")
  if not fh then
    LrDialogs.message("Blink Cull", string.format(S.cannotWrite, listFile), "critical")
    return
  end
  fh:write(table.concat(order, "\n"), "\n")
  fh:close()

  -- 2) run the engine; a second task follows its progress and watches for cancel
  local scope = LrProgressScope { title = S.progress, functionContext = context }
  scope:setCancelable(true)
  local finished = false
  LrTasks.startAsyncTask(function()
    while not finished do
      local txt = readAll(progFile)
      local done, total = (txt or ""):match("(%d+)%s+(%d+)")
      if done then scope:setPortionComplete(tonumber(done), tonumber(total)) end
      if scope:isCanceled() then
        local c = io.open(cancelFile, "wb"); if c then c:write("1"); c:close() end
      end
      LrTasks.sleep(0.5)
    end
  end)

  local cmd = table.concat({ q(opt.engine), "--scan-list", q(listFile), "--out", q(outFile),
                             "--progress", q(progFile), "--cancel", q(cancelFile) }, " ")
  local exitCode = run(cmd)
  finished = true
  local canceled = scope:isCanceled()
  scope:done()

  if canceled then
    LrDialogs.message("Blink Cull", S.canceled, "info")
    return
  end
  local raw = readAll(outFile)
  if exitCode ~= 0 or not raw then
    LrDialogs.message("Blink Cull", string.format(S.engineFailed, tostring(exitCode)), "critical")
    return
  end

  -- 3) results: path <TAB> score <TAB> faces_judged <TAB> status
  local results = {}
  for line in raw:gmatch("[^\r\n]+") do
    local path, score, judged, status = line:match("^(.-)\t(.-)\t(.-)\t(.*)$")
    if path then results[path] = { score = tonumber(score), judged = tonumber(judged) or 0, status = status } end
  end

  local red, yellow, counts = {}, {}, { ok = 0, nojudged = 0, error = 0, missing = 0, kept = 0, labelFailed = 0 }
  for _, path in ipairs(order) do
    local r = results[path]
    if not r then
      counts.error = counts.error + 1
    elseif r.status ~= "ok" then
      counts[r.status] = (counts[r.status] or 0) + 1
    elseif r.score >= closedMin then
      for _, p in ipairs(byPath[path]) do red[#red + 1] = p end
    elseif r.score >= checkMin then
      for _, p in ipairs(byPath[path]) do yellow[#yellow + 1] = p end
    else
      counts.ok = counts.ok + 1
    end
  end

  -- 4) write into the catalog (labels, keywords, collections)
  local stamp = os.date("%Y-%m-%d %H:%M")
  catalog:withWriteAccessDo(S.undoName, function()
    local kwRed, kwYellow
    if opt.addKeywords then
      kwRed = catalog:createKeyword("blinkcull-closed", {}, false, nil, true)
      kwYellow = catalog:createKeyword("blinkcull-check", {}, false, nil, true)
    end
    local function apply(list, label, kw)
      for _, photo in ipairs(list) do
        local current = photo:getFormattedMetadata("label")
        if opt.skipLabeled and current and current ~= "" then
          counts.kept = counts.kept + 1
        else
          local ok = pcall(function() photo:setRawMetadata("label", label) end)
          if not ok then counts.labelFailed = counts.labelFailed + 1 end
        end
        if kw then photo:addKeyword(kw) end
      end
    end
    apply(red, "Red", kwRed)
    apply(yellow, "Yellow", kwYellow)
    if opt.makeCollections then
      if #red > 0 then catalog:createCollection(string.format(S.collRed, stamp), nil, true):addPhotos(red) end
      if #yellow > 0 then catalog:createCollection(string.format(S.collYellow, stamp), nil, true):addPhotos(yellow) end
    end
  end)

  -- 5) summary
  local lines = {
    string.format(S.analyzed, #order),
    string.format(S.redLine, closedMin, #red),
    string.format(S.yellowLine, checkMin, #yellow),
    string.format(S.okLine, counts.ok, counts.nojudged),
  }
  if counts.kept > 0 then lines[#lines + 1] = string.format(S.keptLine, counts.kept) end
  if counts.error + counts.missing > 0 then lines[#lines + 1] = string.format(S.errLine, counts.error + counts.missing) end
  if skippedFormat > 0 then lines[#lines + 1] = string.format(S.skipLine, skippedFormat) end
  if counts.labelFailed > 0 then lines[#lines + 1] = string.format(S.labelFailed, counts.labelFailed) end
  LrDialogs.message(S.doneTitle, table.concat(lines, "\n"), "info")
end)
