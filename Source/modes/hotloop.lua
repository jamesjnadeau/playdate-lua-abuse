-- hotloop: DON'T do per-pixel work in Lua, and DON'T do it with globals.
--
-- Every frame this mode walks a grid of "pixels" in a Lua loop and computes
-- a plasma value for each with math.sin, looked up through globals
-- (HOT_MATH.sin, HOT_W, HOT_SCALE) instead of locals, recomputing the same
-- constants on every iteration. Only the result is drawn, with a handful of
-- calls, so the time is all Lua. Cache globals in locals, hoist constants
-- out of the loop, and draw into an image once instead of recomputing.

local gfx <const> = playdate.graphics

HOT_MATH = math   -- bad: a global alias, looked up on every use
HOT_W = 100       -- grid columns (each cell is 4x4 screen pixels)
HOT_H = 55        -- grid rows
HOT_SCALE = 10

local values = {}
local t = 0

local function plasma()
	for y = 1, HOT_H do
		for x = 1, HOT_W do
			-- bad: constants recomputed inside the loop, every call through globals
			local k = HOT_MATH.pi * 2 / HOT_SCALE
			local v = HOT_MATH.sin(x * k + t) + HOT_MATH.sin(y * k - t) + HOT_MATH.sin((x + y) * k * 0.5)
			values[(y - 1) * HOT_W + x] = v
		end
	end
end

ABUSE_MODES.hotloop = {
	id = "hotloop",
	name = "Hot loop",
	caption = "per-pixel math in Lua via globals",

	enter = function()
		t = 0
	end,

	update = function()
		t += 0.1
		plasma()
		-- Draw a coarse summary: one bar per column, a few dozen calls.
		gfx.clear(gfx.kColorWhite)
		for x = 1, HOT_W, 4 do
			local h = (values[27 * HOT_W + x] + 3) * 30
			gfx.fillRect((x - 1) * 4, 220 - h, 14, h)
		end
	end,

	exit = function()
		values = {}
	end,
}
