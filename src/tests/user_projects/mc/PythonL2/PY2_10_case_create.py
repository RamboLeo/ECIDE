import pygame
import sys

pygame.init()
screen = pygame.display.set_mode((1000, 700))

# 花朵图片列表
wishes = []
eternals = []
mews = []

# 加载背景图片
bg = pygame.image.load('images/bg2.png')
# 加载希望花图片
for i in range(10):
    w = pygame.image.load('images/wish/%d.png' % (i))
    wishes.append(w)
# 加载永恒花图片
for i in range(10):
    e = pygame.image.load('images/eternal/%d.png' % (i))
    eternals.append(e)
# 加载梦幻花图片
for i in range(10):
    m = pygame.image.load('images/mew/%d.png' % (i))
    mews.append(m)

# 请在下方编写代码
i = 0
while True:
    screen.blit(bg,(0,0))
    # 请在下方编写代码
    screen.blit(wishes[i],(370,330))
    i += 1
    if i == 10:
        i = 9
    pygame.time.delay(500)
    # 事件获取
    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            sys.exit()
    pygame.display.update()
