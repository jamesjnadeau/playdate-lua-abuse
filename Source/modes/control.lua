-- control: the well-behaved baseline.
--
-- A handful of sprites bounce around. The background is drawn by the sprite
-- system's background callback, so only the rectangles the sprites touch
-- are redrawn each frame. Nothing is allocated per frame. This mode should
-- never go over budget: it shows the simulator doesn't cry wolf.

local gfx <const> = playdate.graphics

local COUNT <const> = 8

local ballImage = nil
local balls = {}

local function bounce(s)
	local x, y = s.x + s.dx, s.y + s.dy
	if x < 8 or x > 392 then s.dx = -s.dx end
	if y < 8 or y > 214 then s.dy = -s.dy end
	s:moveTo(x, y)
end

ABUSE_MODES.control = {
	id = "control",
	name = "Control",
	caption = "well-behaved baseline",

	enter = function()
		if not ballImage then
			ballImage = gfx.image.new(16, 16)
			gfx.pushContext(ballImage)
			gfx.fillCircleAtPoint(8, 8, 7)
			gfx.popContext()
		end
		gfx.sprite.setBackgroundDrawingCallback(function(x, y, w, h)
			gfx.setColor(gfx.kColorWhite)
			gfx.fillRect(x, y, w, h)
			gfx.setColor(gfx.kColorBlack)
		end)
		for i = 1, COUNT do
			local s = gfx.sprite.new(ballImage)
			s.dx = (i % 3) + 1
			s.dy = ((i + 1) % 3) + 1
			s.update = bounce
			s:moveTo(40 + i * 40, 30 + (i * 23) % 170)
			s:add()
			balls[i] = s
		end
	end,

	update = function()
		gfx.sprite.update()
	end,

	exit = function()
		for i = 1, #balls do balls[i]:remove(); balls[i] = nil end
	end,
}
