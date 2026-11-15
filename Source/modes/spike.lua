-- spike: DON'T do a burst of allocation every so often.
--
-- Most frames here are cheap. But once every PERIOD frames the mode builds a
-- big table of small tables in one go (think: rebuilding a level, or loading
-- a wave of enemies) and drops it. That frame, and the garbage collection
-- that follows, blow the budget: a regular hitch the player feels even though
-- the average frame time looks fine. Spread the work over several frames,
-- build it once and reuse it, or do it behind a loading screen.

local gfx <const> = playdate.graphics

local PERIOD <const> = 60     -- frames between spikes
local ENTRIES <const> = 40000 -- tables built in a spike frame

local modeFrame = 0
local x = 0

ABUSE_MODES.spike = {
	id = "spike",
	name = "Spike",
	caption = "a big allocation burst every 60 frames",

	enter = function()
		modeFrame = 0
		x = 0
	end,

	update = function()
		modeFrame += 1
		if modeFrame % PERIOD == 0 then
			-- Bad: all of it at once, then thrown away.
			local wave = {}
			for i = 1, ENTRIES do wave[i] = { x = i, y = i } end
			wave = nil
		end

		x = (x + 2) % 380
		gfx.clear(gfx.kColorWhite)
		gfx.fillRect(x, 100, 20, 20)
	end,

	exit = function() end,
}
