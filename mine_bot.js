/**
 * mine_bot.js — Фитц-бот для Майнкрафта 1.5.0
 * Подключается через mineflayer, выполняет команды из mc_to_bot.txt,
 * периодически пишет состояние мира в mc_from_bot.txt (JSON).
 *
 * Команды: FOLLOW, DIG, ATTACK, EAT, STOP, JUMP, SAY:text
 *
 * Установка: npm install mineflayer mineflayer-pathfinder
 */
const mineflayer = require('mineflayer')
const { pathfinder, Movements, goals } = require('mineflayer-pathfinder')
const fs = require('fs')
const path = require('path')

const args = process.argv.slice(2)
const host = args[0] || 'localhost'
const port = parseInt(args[1]) || 34485
const nick = args[2] || 'FitzBot'

const TO_BOT_FILE = path.join(__dirname, 'data', 'mc_to_bot.txt')
const FROM_BOT_FILE = path.join(__dirname, 'data', 'mc_from_bot.txt')
const STATE_INTERVAL = 2000 // каждые 2 секунды пишем состояние

// Атомарная запись (через tmp + rename)
function atomicWrite(filePath, data) {
  const tmp = filePath + '.tmp'
  try {
    fs.writeFileSync(tmp, data, 'utf8')
    fs.renameSync(tmp, filePath)
  } catch (e) {
    // Тихо игнорируем ошибки записи
  }
}

const bot = mineflayer.createBot({
  host: host,
  port: port,
  username: nick,
  auth: 'offline',
  version: '1.12.2' // более современная версия
})

// ===== ЗАГРУЖАЕМ PATHFINDER =====
bot.loadPlugin(pathfinder)

// ===== СОСТОЯНИЕ =====
let mcData = null

// ===== НАСТРОЙКА ПОСЛЕ СПАВНА =====
bot.once('spawn', () => {
  console.log('✅ Фитц-бот зашёл в игру!')
  bot.chat('Привет, создатель! Я тут.')

  // Ждём загрузки registry
  const setupPathfinder = () => {
    try {
      if (!bot.registry || !bot.registry.blocksByName) {
        console.log('⏳ Жду registry...')
        setTimeout(setupPathfinder, 1000)
        return
      }
      mcData = require('minecraft-data')(bot.version)
      const defaultMove = new Movements(bot, mcData)
      defaultMove.canDig = true
      defaultMove.allowParkour = false
      defaultMove.allow1by1towers = false
      defaultMove.scafoldingBlocks = []
      bot.pathfinder.setMovements(defaultMove)
      console.log('✅ Pathfinder настроен!')
    } catch (e) {
      console.log('⚠️ Ошибка pathfinder:', e.message)
    }
  }
  setTimeout(setupPathfinder, 2000)
})

// ===== ЧТЕНИЕ КОМАНД ОТ PYTHON =====
setInterval(() => {
  try {
    if (!fs.existsSync(TO_BOT_FILE)) return
    const content = fs.readFileSync(TO_BOT_FILE, 'utf8').trim()
    if (!content) return

    console.log(`🎮 Команда: ${content}`)
    executeAction(content)
    // Очищаем команду атомарно
    atomicWrite(TO_BOT_FILE, '')
  } catch (e) {
    // Игнорируем ошибки чтения
  }
}, 1000)

// ===== ПЕРИОДИЧЕСКАЯ ОТПРАВКА СОСТОЯНИЯ =====
setInterval(() => {
  try {
    const entity = bot.entity
    if (!entity) return

    // Ближайший игрок
    let nearestPlayer = 'нет'
    let nearestPlayerDist = Infinity
    for (const [id, player] of Object.entries(bot.players)) {
      if (player.username === bot.username) continue
      if (player.entity) {
        const dist = entity.position.distanceTo(player.entity.position)
        if (dist < nearestPlayerDist) {
          nearestPlayerDist = dist
          nearestPlayer = player.username
        }
      }
    }

    // Ближайший моб
    let nearestMob = 'нет'
    let nearestMobDist = Infinity
    const mobs = Object.values(bot.entities).filter(e =>
      e.type === 'mob' && e !== entity
    )
    for (const mob of mobs) {
      const dist = entity.position.distanceTo(mob.position)
      if (dist < nearestMobDist) {
        nearestMobDist = dist
        nearestMob = mob.name || mob.type || 'моб'
      }
    }

    // Есть ли дерево рядом (радиус 5 блоков)
    let hasWoodNearby = false
    const pos = entity.position
    if (bot.findBlock) {
      const woodBlock = bot.findBlock({
        matching: (block) => {
          if (!block || !block.name) return false
          return block.name.includes('log') || block.name.includes('wood')
        },
        maxDistance: 8
      })
      hasWoodNearby = !!woodBlock
    }

    const state = {
      health: Math.round(entity.health || 20),
      food: Math.round(entity.food || 20),
      pos: pos ? `${Math.round(pos.x)} ${Math.round(pos.y)} ${Math.round(pos.z)}` : '?',
      nearestPlayer: nearestPlayer,
      nearestMob: nearestMob,
      hasWoodNearby: hasWoodNearby,
      time: new Date().toISOString()
    }

    atomicWrite(FROM_BOT_FILE, JSON.stringify(state))
  } catch (e) {
    console.log('⚠️ Ошибка состояния:', e.message)
  }
}, STATE_INTERVAL)

// ===== ВЫПОЛНЕНИЕ КОМАНД =====
function executeAction(action) {
  const upper = action.toUpperCase().trim()

  if (upper === 'FOLLOW') {
    const players = Object.values(bot.players).filter(p =>
      p.username !== bot.username && p.entity
    )
    if (players.length === 0) {
      console.log('❌ Игроков нет рядом')
      return
    }
    players.sort((a, b) => {
      const da = bot.entity.position.distanceTo(a.entity.position)
      const db = bot.entity.position.distanceTo(b.entity.position)
      return da - db
    })
    const target = players[0]
    console.log(`🎮 Иду за ${target.username}`)
    try {
      bot.pathfinder.setGoal(new goals.GoalFollow(target.entity, 2), true)
    } catch (e) {
      console.log('❌ Ошибка FOLLOW:', e.message)
    }
  }
  else if (upper === 'STOP') {
    console.log('🎮 Стою')
    bot.pathfinder.setGoal(null)
    bot.clearControlStates()
  }
  else if (upper === 'DIG') {
    console.log('🎮 Копаю дерево')
    if (bot.findBlock && mcData) {
      const woodBlock = bot.findBlock({
        matching: mcData.blocksByName.log ? [mcData.blocksByName.log.id] : null,
        matching: (block) => {
          return block && block.name && (block.name.includes('log') || block.name.includes('wood'))
        },
        maxDistance: 5
      })
      if (woodBlock) {
        bot.pathfinder.setGoal(new goals.GoalBlock(woodBlock.position.x, woodBlock.position.y, woodBlock.position.z))
        bot.lookAt(woodBlock.position)
        setTimeout(() => {
          if (bot.canDigBlock(woodBlock)) {
            bot.dig(woodBlock, (err) => {
              if (err) console.log('❌ Ошибка копания:', err.message)
              else console.log('✅ Блок срублен')
            })
          }
        }, 1000)
      } else {
        console.log('❌ Дерева рядом нет')
      }
    } else {
      // Fallback: копаем блок под ногами
      const block = bot.blockAt(bot.entity.position.offset(0, -1, 0))
      if (block && bot.canDigBlock(block)) {
        bot.dig(block, (err) => {
          if (err) console.log('❌ Ошибка:', err.message)
          else console.log('✅ Блок сломан')
        })
      }
    }
  }
  else if (upper === 'ATTACK') {
    console.log('🎮 Атакую ближайшего моба')
    const mobs = Object.values(bot.entities).filter(e =>
      e.type === 'mob' && e !== bot.entity
    )
    if (mobs.length === 0) {
      console.log('❌ Мобов рядом нет')
      return
    }
    // Сортируем по расстоянию
    mobs.sort((a, b) => {
      return bot.entity.position.distanceTo(a.position) - bot.entity.position.distanceTo(b.position)
    })
    const target = mobs[0]
    console.log(`🎮 Атакую ${target.name || 'моба'}`)
    bot.lookAt(target.position)
    bot.attack(target)
  }
  else if (upper === 'EAT') {
    console.log('🎮 Ем еду')
    // Ищем еду в инвентаре
    const foodItem = bot.inventory.items().find(item => {
      return item && item.name && (
        item.name.includes('beef') || item.name.includes('porkchop') ||
        item.name.includes('chicken') || item.name.includes('mutton') ||
        item.name.includes('bread') || item.name.includes('apple') ||
        item.name.includes('carrot') || item.name.includes('potato') ||
        item.name.includes('fish') || item.name.includes('salmon') ||
        item.name.includes('cod') || item.name.includes('golden_apple')
      )
    })
    if (foodItem) {
      bot.equip(foodItem, 'hand', (err) => {
        if (err) {
          console.log('❌ Ошибка экипировки:', err.message)
          return
        }
        bot.consume((err) => {
          if (err) console.log('❌ Ошибка еды:', err.message)
          else console.log('✅ Поел!')
        })
      })
    } else {
      console.log('❌ Еды в инвентаре нет')
    }
  }
  else if (upper === 'JUMP') {
    console.log('🎮 Прыгаю')
    bot.setControlState('jump', true)
    setTimeout(() => bot.setControlState('jump', false), 500)
  }
  else if (upper.startsWith('SAY:')) {
    const text = action.substring(4).trim()
    console.log(`💬 Бот говорит: ${text}`)
    bot.chat(text)
  }
  else {
    // Неизвестная команда
    console.log(`⚠️ Неизвестная команда: ${action}`)
  }
}

// ===== ЧАТ: пересылаем сообщения Python =====
bot.on('chat', (username, message) => {
  if (username === bot.username) return
  try {
    fs.appendFileSync(FROM_BOT_FILE, `\n[Игра] ${username}: ${message}`)
  } catch (e) {}
})

// ===== ОШИБКИ =====
bot.on('kicked', (reason) => {
  const msg = typeof reason === 'string' ? reason : JSON.stringify(reason)
  console.log('❌ Кикнут:', msg)
  atomicWrite(FROM_BOT_FILE, `❌ Кикнут: ${msg}`)
})

bot.on('error', (err) => {
  console.log('⚠️ Ошибка:', err.message)
  atomicWrite(FROM_BOT_FILE, `❌ Ошибка бота: ${err.message}`)
})

bot.on('end', (reason) => {
  console.log('🛑 Бот отключился:', reason)
  atomicWrite(FROM_BOT_FILE, `❌ Бот отключился: ${reason}`)
})

// ===== ЗДОРОВЬЕ И ГОЛОД =====
bot.on('health', () => {
  // Если здоровье низкое — можно попросить Python прислать EAT
  if (bot.entity && bot.entity.food < 6) {
    console.log('🍖 Мало еды! Жду команду EAT...')
  }
})

console.log(`🛡️ Фитц-бот 1.5.0 запущен: ${host}:${port} (${nick})`)