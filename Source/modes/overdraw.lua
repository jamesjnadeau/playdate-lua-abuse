-- overdraw: DON'T clear and repaint the whole static screen every frame.
--
-- Every frame this mode wipes the screen and rebuilds a scene that never
-- changes: a stack of full-screen layers, each one drawn rotated by a fixed
-- tilt (so every pixel is resampled), then a block of text, before drawing
-- one small moving box on top. Every row of the display is dirty every frame
-- and nearly every pixel pushed is the same as last frame. Composite the
-- static scene into one image once (or use sprites and dirty rects) and only
-- redraw what moved.

local gfx <const> = playdate.graphics

local LAYERS <const> = 48      -- full-screen rotated layers per frame
local TILT <const> = 3         -- degrees; fixed, so the result never changes
local TEXT_LINES <const> = 10  -- lines of static text repainted per frame

local layer = nil
local x = 0

local function makeLayer()
	layer = gfx.image.new(400, 240)
	gfx.pushContext(layer)
	gfx.setDitherPattern(0.75, gfx.image.kDitherTypeBayer8x8)
	for gx = 0, 400, 40 do gfx.fillRect(gx, 0, 20, 240) end
	gfx.popContext()
end

ABUSE_MODES.overdraw = {
	id = "overdraw",
	name = "Overdraw",
	caption = "repaint the whole static screen every frame",

	enter = function()
		x = 0
		if not layer then makeLayer() end
	end,

	update = function()
		x = (x + 3) % 380
		gfx.clear(gfx.kColorWhite)

		-- Bad: the same static layers, re-rotated and repainted every frame.
		for _ = 1, LAYERS do
			layer:drawRotated(200, 120, TILT)
		end
		gfx.setColor(gfx.kColorBlack)
		for i = 1, TEXT_LINES do
			gfx.drawText("This text never changes, but it is drawn every frame.", 8, i * 20)
		end

		-- The only thing that actually changes.
		gfx.fillRect(x, 100, 20, 20)
	end,

	exit = function() end,
}
