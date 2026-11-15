-- disk: DON'T save to disk every frame.
--
-- Every frame this mode updates a batch of scores and, after each change,
-- writes the player's progress to the data folder with
-- playdate.datastore.write. Every write opens, encodes and rewrites a file on
-- flash, which is slow and blocks the frame. Keep progress in memory and save
-- when something meaningful happens (a checkpoint, the menu,
-- playdate.gameWillTerminate), not after every change.

local gfx <const> = playdate.graphics

local CHANGES <const> = 100   -- score changes (and so saves) per frame

local progress = { frame = 0, last = 0, score = 0 }
local frame = 0

ABUSE_MODES.disk = {
	id = "disk",
	name = "Disk",
	caption = "save after every change, every frame",

	enter = function()
		frame = 0
		progress.frame, progress.last, progress.score = 0, 0, 0
	end,

	update = function()
		frame += 1
		progress.frame = frame
		for i = 1, CHANGES do
			progress.last = i
			progress.score += 1
			-- Bad: a save after every single change.
			playdate.datastore.write(progress, "abuse-disk")
		end

		gfx.clear(gfx.kColorWhite)
		gfx.drawText("saved " .. progress.score .. " times", 8, 8)
	end,

	exit = function() end,
}
