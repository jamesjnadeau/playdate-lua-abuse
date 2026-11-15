-- Lua Abuse: one mode per bad Lua performance idea.
--
-- Each mode lives in modes/<id>.lua and registers itself in ABUSE_MODES:
--   { id, name, caption, enter(), update(), exit() }
-- update() does all of the mode's drawing for the frame.
--
-- Mode selection:
--   * config.json in the data folder: {"mode": "<id>"} runs one mode directly,
--     {"mode": "auto", "cycleFrames": N} runs the auto-cycle.
--   * otherwise a menu: up/down or crank to move, A to start, B to go back.

import "CoreLibs/object"
import "CoreLibs/graphics"
import "CoreLibs/sprites"
import "CoreLibs/timer"

ABUSE_MODES = {}

import "modes/control"
import "modes/garbage"
import "modes/hotloop"
import "modes/overdraw"

local gfx <const> = playdate.graphics

-- Display order. Ids that aren't registered (yet) are skipped.
local ORDER <const> = { "control", "garbage", "hotloop", "overdraw", "sprites", "disk", "spike" }

local MODES = {}
for _, id in ipairs(ORDER) do
	if ABUSE_MODES[id] then MODES[#MODES + 1] = ABUSE_MODES[id] end
end

local OVERLAY_H <const> = 18

local function drawOverlay(mode, extra)
	local y = 240 - OVERLAY_H
	gfx.setColor(gfx.kColorWhite)
	gfx.fillRect(0, y, 400, OVERLAY_H)
	gfx.setColor(gfx.kColorBlack)
	gfx.drawLine(0, y, 400, y)
	local text = mode.name .. ": " .. mode.caption
	if extra then text = extra .. "  " .. text end
	gfx.drawText(text, 4, y + 2)
end

-- State ---------------------------------------------------------------------

local state = "menu"     -- "menu" | "mode"
local current = nil      -- active mode table
local selected = 1       -- menu cursor (1..#MODES + 1, last is auto-cycle)
local menuDirty = true
local crankAccum = 0

local function startMode(mode)
	gfx.clear(gfx.kColorWhite)
	current = mode
	state = "mode"
	mode.enter()
end

local function stopMode()
	if current then current.exit() end
	current = nil
	gfx.sprite.removeAll()
	gfx.clear(gfx.kColorWhite)
	state = "menu"
	menuDirty = true
end

-- Menu ----------------------------------------------------------------------

local function menuItemCount() return #MODES + 1 end

local function drawMenu()
	gfx.clear(gfx.kColorWhite)
	gfx.drawText("*Lua Abuse*", 16, 8)
	for i = 1, menuItemCount() do
		local label = (i <= #MODES) and (MODES[i].name .. " - " .. MODES[i].caption) or "Auto-cycle"
		local y = 30 + (i - 1) * 22
		if i == selected then
			gfx.fillRect(8, y - 2, 384, 20)
			gfx.setImageDrawMode(gfx.kDrawModeFillWhite)
			gfx.drawText(label, 16, y)
			gfx.setImageDrawMode(gfx.kDrawModeCopy)
		else
			gfx.drawText(label, 16, y)
		end
	end
	menuDirty = false
end

local function moveSelection(delta)
	local n = menuItemCount()
	selected = ((selected - 1 + delta) % n) + 1
	menuDirty = true
end

local startAuto -- defined with auto-cycle below

local function updateMenu()
	if playdate.buttonJustPressed(playdate.kButtonUp) then moveSelection(-1) end
	if playdate.buttonJustPressed(playdate.kButtonDown) then moveSelection(1) end
	crankAccum += playdate.getCrankChange()
	while crankAccum >= 30 do moveSelection(1); crankAccum -= 30 end
	while crankAccum <= -30 do moveSelection(-1); crankAccum += 30 end
	if playdate.buttonJustPressed(playdate.kButtonA) then
		if selected <= #MODES then startMode(MODES[selected]) else startAuto() end
		return
	end
	if menuDirty then drawMenu() end
end

-- Auto-cycle (stub until implemented) ----------------------------------------

startAuto = function()
	menuDirty = true
end

-- Startup -------------------------------------------------------------------

local cfg = playdate.datastore.read("config")
if cfg and cfg.mode then
	if cfg.mode == "auto" then
		startAuto(cfg.cycleFrames)
	elseif ABUSE_MODES[cfg.mode] then
		startMode(ABUSE_MODES[cfg.mode])
	end
end

function playdate.update()
	if state == "menu" then
		updateMenu()
	else
		if playdate.buttonJustPressed(playdate.kButtonB) then
			stopMode()
			return
		end
		current.update()
		drawOverlay(current)
	end
	playdate.timer.updateTimers()
end
