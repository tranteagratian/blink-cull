-- Blink Cull pentru Lightroom Classic.
-- Ia pozele selectate, le da motorului Blink Cull (aplicatia, in modul fara interfata) si pune in catalog
-- eticheta de culoare (rosu / galben), cuvinte cheie si colectii. NU sterge, NU respinge si NU modifica fisierele RAW.

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

local function q(s) return '"' .. s .. '"' end

local function run(cmd)
  if WIN_ENV then cmd = '"' .. cmd .. '"' end  -- cmd.exe vrea o pereche de ghilimele in jurul intregii comenzi
  return LrTasks.execute(cmd)
end

local function readAll(path)
  local fh = io.open(path, "rb")
  if not fh then return nil end
  local s = fh:read("*a")
  fh:close()
  return s
end

local function defaultEngine()
  local home = LrPathUtils.getStandardFilePath("home")
  local candidates = {
    "/Applications/Blink Cull.app/Contents/MacOS/Blink Cull",
    home .. "/Applications/Blink Cull.app/Contents/MacOS/Blink Cull",
    home .. "/blink-cull/dist/Blink Cull.app/Contents/MacOS/Blink Cull",
    "C:\\Program Files\\Blink Cull\\Blink Cull.exe",
  }
  for _, c in ipairs(candidates) do
    if LrFileUtils.exists(c) == "file" then return c end
  end
  return candidates[1]
end

local function showDialog(context, count)
  local f = LrView.osFactory()
  local props = LrBinding.makePropertyTable(context)
  props.engine = prefs.engine or defaultEngine()
  props.closedMin = prefs.closedMin or 0.45
  props.checkMin = prefs.checkMin or 0.25
  props.skipLabeled = (prefs.skipLabeled ~= false)
  props.addKeywords = (prefs.addKeywords ~= false)
  props.makeCollections = (prefs.makeCollections ~= false)

  local contents = f:column {
    bind_to_object = props,
    spacing = f:control_spacing(),
    f:static_text { title = string.format("Se analizează %d poze selectate (doar fișiere ARW).", count) },
    f:row {
      f:static_text { title = "Motorul Blink Cull:", width = 130 },
      f:edit_field { value = LrView.bind("engine"), width_in_chars = 55 },
    },
    f:row {
      f:static_text { title = "Roșu (sigur) la scor ≥", width = 130 },
      f:edit_field { value = LrView.bind("closedMin"), width_in_chars = 5, precision = 2, min = 0, max = 1 },
      f:static_text { title = "   Galben (de verificat) la scor ≥" },
      f:edit_field { value = LrView.bind("checkMin"), width_in_chars = 5, precision = 2, min = 0, max = 1 },
    },
    f:checkbox { title = "Nu schimba pozele care au deja o etichetă de culoare", value = LrView.bind("skipLabeled") },
    f:checkbox { title = "Adaugă cuvinte cheie (blinkcull-inchis / blinkcull-verifica)", value = LrView.bind("addKeywords") },
    f:checkbox { title = "Creează colecții cu pozele găsite (ușor de parcurs în grilă)", value = LrView.bind("makeCollections") },
  }

  local result = LrDialogs.presentModalDialog {
    title = "Blink Cull: ochi închiși",
    contents = contents,
    actionVerb = "Analizează",
  }
  if result ~= "ok" then return nil end
  for _, k in ipairs { "engine", "closedMin", "checkMin", "skipLabeled", "addKeywords", "makeCollections" } do
    prefs[k] = props[k]
  end
  return props
end

LrFunctionContext.postAsyncTaskWithContext("BlinkCull", function(context)
  local catalog = LrApplication.activeCatalog()
  local photos = catalog:getTargetPhotos()
  if #photos == 0 then
    LrDialogs.message("Blink Cull", "Nu e nicio poză selectată. Selectează pozele (sau un folder) și rulează din nou.", "info")
    return
  end

  local opt = showDialog(context, #photos)
  if not opt then return end
  local closedMin, checkMin = tonumber(opt.closedMin) or 0.45, tonumber(opt.checkMin) or 0.25
  if LrFileUtils.exists(opt.engine) ~= "file" then
    LrDialogs.message("Blink Cull", "Nu găsesc motorul Blink Cull la:\n" .. tostring(opt.engine) ..
      "\n\nInstalează aplicația Blink Cull și completează calea corectă în fereastra de dialog.", "critical")
    return
  end

  -- 1) lista de poze: cale -> pozele din catalog care o folosesc (copiile virtuale impart aceeasi cale)
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
    LrDialogs.message("Blink Cull", "Nicio poză selectată nu e în format ARW (Sony RAW). Momentan doar ARW e acceptat.", "info")
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
    LrDialogs.message("Blink Cull", "Nu pot scrie fișierul temporar:\n" .. listFile, "critical")
    return
  end
  fh:write(table.concat(order, "\n"), "\n")
  fh:close()

  -- 2) rulam motorul, iar intr-un alt task urmarim progresul si anularea
  local scope = LrProgressScope { title = "Blink Cull: analizez pozele", functionContext = context }
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
    LrDialogs.message("Blink Cull", "Analiza a fost anulată. Nu am modificat nimic în catalog.", "info")
    return
  end
  local raw = readAll(outFile)
  if exitCode ~= 0 or not raw then
    LrDialogs.message("Blink Cull", "Motorul nu a terminat analiza (cod " .. tostring(exitCode) ..
      ").\nVerifică calea motorului și încearcă din nou. Nu am modificat nimic în catalog.", "critical")
    return
  end

  -- 3) rezultatele: cale <TAB> scor <TAB> fete_judecate <TAB> stare
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

  -- 4) scriem in catalog (etichete, cuvinte cheie, colectii)
  local stamp = os.date("%Y-%m-%d %H:%M")
  catalog:withWriteAccessDo("Blink Cull: etichete", function()
    local kwRed, kwYellow
    if opt.addKeywords then
      kwRed = catalog:createKeyword("blinkcull-inchis", {}, false, nil, true)
      kwYellow = catalog:createKeyword("blinkcull-verifica", {}, false, nil, true)
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
      if #red > 0 then catalog:createCollection("Blink Cull " .. stamp .. " – roșii (sigur)", nil, true):addPhotos(red) end
      if #yellow > 0 then catalog:createCollection("Blink Cull " .. stamp .. " – galbene (de verificat)", nil, true):addPhotos(yellow) end
    end
  end)

  -- 5) rezumat
  local lines = {
    string.format("Analizate: %d poze ARW.", #order),
    string.format("Roșii (ochi închiși, scor ≥ %.2f): %d", closedMin, #red),
    string.format("Galbene (de verificat, scor ≥ %.2f): %d", checkMin, #yellow),
    string.format("Fără probleme: %d | fără fețe judecate: %d", counts.ok, counts.nojudged),
  }
  if counts.kept > 0 then lines[#lines + 1] = string.format("Păstrate cu eticheta lor deja existentă: %d", counts.kept) end
  if counts.error + counts.missing > 0 then lines[#lines + 1] = string.format("Erori / fișiere lipsă: %d", counts.error + counts.missing) end
  if skippedFormat > 0 then lines[#lines + 1] = string.format("Ignorate (nu sunt ARW): %d", skippedFormat) end
  if counts.labelFailed > 0 then
    lines[#lines + 1] = string.format("ATENȚIE: nu am putut seta eticheta de culoare la %d poze (cuvintele cheie și colecțiile au fost aplicate).", counts.labelFailed)
  end
  LrDialogs.message("Blink Cull: gata", table.concat(lines, "\n"), "info")
end)
