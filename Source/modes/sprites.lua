-- sprites: DON'T give a hundred sprites their own update and collisions.
--
-- Every bullet here is its own sprite subclass instance with a Lua update()
-- override, a collide rect, and a moveWithCollisions() call every frame. The
-- sprite system walks, sorts, collision-tests and redraws every one of them.
-- A hundred identical things moving the same way should be one image (or
-- one sprite drawing many) updated by one loop, with collisions only where
-- they matter.

local gfx <const> = playdate.graphics

local COUNT <const> = 100

class("AbuseBullet").extends(gfx.sprite)

local bulletImage = nil
local bullets = {}

function AbuseBullet:init(i)
	AbuseBullet.super.init(self, bulletImage)
	self.dx = (i % 5) - 2
	self.dy = ((i * 7) % 5) - 2
	if self.dx == 0 then self.dx = 1 end
	self:setCollideRect(0, 0, 6, 6)
	self:moveTo(10 + (i * 37) % 380, 10 + (i * 53) % 200)
	self:add()
end

function AbuseBullet:collisionResponse()
	return gfx.sprite.kCollisionTypeOverlap
end

function AbuseBullet:update()
	local x, y = self.x + self.dx, self.y + self.dy
	if x < 3 or x > 397 then self.dx = -self.dx end
	if y < 3 or y > 218 then self.dy = -self.dy end
	self:moveWithCollisions(x, y)
end

ABUSE_MODES.sprites = {
	id = "sprites",
	name = "Sprites",
	caption = "100 sprites, each with its own update and collisions",

	enter = function()
		if not bulletImage then
			bulletImage = gfx.image.new(6, 6)
			gfx.pushContext(bulletImage)
			gfx.fillRect(0, 0, 6, 6)
			gfx.popContext()
		end
		gfx.sprite.setBackgroundDrawingCallback(function(x, y, w, h)
			gfx.setColor(gfx.kColorWhite)
			gfx.fillRect(x, y, w, h)
			gfx.setColor(gfx.kColorBlack)
		end)
		for i = 1, COUNT do bullets[i] = AbuseBullet(i) end
	end,

	update = function()
		gfx.sprite.update()
	end,

	exit = function()
		for i = 1, #bullets do bullets[i]:remove(); bullets[i] = nil end
	end,
}
