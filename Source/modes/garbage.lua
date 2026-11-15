-- garbage: DON'T allocate fresh tables, closures and strings every frame.
--
-- Every frame this mode builds thousands of little {x=, y=} tables, wraps
-- each in a brand-new closure, and assembles a status string one `..` at a
-- time. Nothing is kept, so it's all garbage by the next frame and the
-- collector has to chase it. Reuse tables, hoist closures out of the loop
-- and use table.concat (or string.format) instead.

local gfx <const> = playdate.graphics

local PARTICLES <const> = 300   -- tables + closures allocated per frame
local LABEL_PARTS <const> = 3000  -- string pieces glued with `..` per frame

local frame = 0

ABUSE_MODES.garbage = {
	id = "garbage",
	name = "Garbage",
	caption = "fresh tables, closures, strings every frame",

	enter = function()
		frame = 0
	end,

	update = function()
		frame += 1
		gfx.clear(gfx.kColorWhite)

		-- Bad: a new table and a new closure for every particle, every frame.
		local particles = {}
		for i = 1, PARTICLES do
			local p = { x = (i * 7 + frame) % 400, y = (i * 13 + frame * 2) % 220 }
			p.draw = function() return p.x, p.y end
			particles[i] = p
		end
		for i = 1, #particles, 25 do
			local x, y = particles[i].draw()
			gfx.fillRect(x, y, 2, 2)
		end

		-- Bad: building a string one `..` at a time makes a new string each step.
		local label = ""
		for i = 1, LABEL_PARTS do
			label = label .. "#"
		end
		gfx.drawText("frame " .. frame .. " " .. #label, 8, 8)
	end,

	exit = function() end,
}
