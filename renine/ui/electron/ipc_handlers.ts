/**
 * Renine — IPC Event Handlers
 *
 * Handles IPC messages from the renderer process and bridges
 * them to the Python backend (via subprocess pipe).
 */

import { ipcMain, BrowserWindow } from 'electron';
import * as path from 'path';

/**
 * Execute a Python script segment in the project environment.
 * Uses stdin pipe to prevent escaping issues on Windows shell.
 */
function runPython(code: string): Promise<any> {
    return new Promise((resolve, reject) => {
        const spawn = require('child_process').spawn;
        const workspaceRoot = path.resolve(__dirname, '..', '..', '..');
        const env = { ...process.env, PYTHONPATH: workspaceRoot };
        const child = spawn('python', ['-c', 'import sys; exec(sys.stdin.read())'], {
            cwd: workspaceRoot,
            env,
        });

        let stdout = '';
        let stderr = '';

        child.stdout.on('data', (data: Buffer) => {
            stdout += data.toString();
        });

        child.stderr.on('data', (data: Buffer) => {
            stderr += data.toString();
        });

        child.on('close', (code: number) => {
            if (code !== 0) {
                console.error('[Python Subprocess Error]', stderr);
                reject(new Error(`Python process exited with code ${code}. Error: ${stderr}`));
            } else {
                try {
                    resolve(JSON.parse(stdout.trim()));
                } catch (e) {
                    console.error('[Python JSON Parse Error] Output was:', stdout);
                    resolve({ success: false, raw: stdout });
                }
            }
        });

        child.stdin.write(code);
        child.stdin.end();
    });
}

/**
 * Register all IPC handlers for the main process.
 */
export function registerIpcHandlers(): void {
    ipcMain.on('renine:send-message', async (_event, data: { text: string }) => {
        console.log('[IPC] Message received:', data.text);

        try {
            const pythonCode = `
import json
from renine.brain.router import route, RouteTarget
from renine.agents.main_brain_agent import MainBrainAgent
from renine.agents.inventory_agent import InventoryAgent
from renine.agents.pet_agent import PetAgent
from renine.agents.house_agent import HouseAgent
from renine.agents.browser_agent import BrowserAgent
from renine.agents.email_agent import EmailAgent
from renine.agents.news_agent import NewsAgent

user_input = ${JSON.stringify(data.text)}
decision = route(user_input)

if decision.target == RouteTarget.INVENTORY_AGENT:
    agent = InventoryAgent()
elif decision.target == RouteTarget.PET_AGENT:
    agent = PetAgent()
elif decision.target == RouteTarget.HOUSE_AGENT:
    agent = HouseAgent()
elif decision.target == RouteTarget.BROWSER_AGENT:
    agent = BrowserAgent()
elif decision.target == RouteTarget.EMAIL_AGENT:
    agent = EmailAgent()
elif decision.target == RouteTarget.NEWS_AGENT:
    agent = NewsAgent()
else:
    agent = MainBrainAgent()

res = agent.process(user_input)
print(json.dumps(res))
`;
            const result = await runPython(pythonCode);
            const windows = BrowserWindow.getAllWindows();
            if (windows.length > 0) {
                windows[0].webContents.send('renine:receive-response', {
                    content: result.content || "I couldn't process that command.",
                    source: result.source_agent || 'main_brain',
                    timestamp: Date.now(),
                });
            }
        } catch (error: any) {
            console.error('[IPC] Message execution failed:', error);
            const windows = BrowserWindow.getAllWindows();
            if (windows.length > 0) {
                windows[0].webContents.send('renine:receive-response', {
                    content: `Error: ${error.message}`,
                    source: 'main_brain',
                    timestamp: Date.now(),
                });
            }
        }
    });

    ipcMain.on('renine:voice-toggle', (_event, data: { enabled: boolean }) => {
        console.log('[IPC] Voice toggle:', data.enabled);

        const windows = BrowserWindow.getAllWindows();
        if (windows.length > 0) {
            windows[0].webContents.send('renine:voice-state', {
                state: data.enabled ? 'listening' : 'idle',
            });
        }
    });

    ipcMain.handle('renine:request-status', async () => {
        return {
            status: 'online',
            phase: 6,
            version: '0.6.0',
        };
    });

    ipcMain.handle('renine:db-action', async (_event, data: { action: string; payload: any }) => {
        console.log('[IPC] Database action:', data.action, data.payload);
        try {
            let pythonCode = '';
            if (data.action === 'get-inventory') {
                pythonCode = `
import json
from renine.agents.inventory_agent import InventoryAgent
agent = InventoryAgent()
items = [{'name': i.name, 'category': i.category, 'quantity': i.quantity, 'unit': i.unit, 'threshold': i.threshold, 'location': i.location, 'expiration_date': i.expiration_date.isoformat() if i.expiration_date else None} for i in agent.list_items()]
print(json.dumps(items))
`;
            } else if (data.action === 'add-inventory') {
                const p = data.payload;
                pythonCode = `
import json
from renine.agents.inventory_agent import InventoryAgent
agent = InventoryAgent()
item = agent.add_item(
    name=${JSON.stringify(p.name)},
    category=${JSON.stringify(p.category)},
    quantity=float(${p.quantity}),
    unit=${JSON.stringify(p.unit)},
    threshold=float(${p.threshold}),
    location=${JSON.stringify(p.location)}
)
print(json.dumps({'success': True, 'name': item.name}))
`;
            } else if (data.action === 'delete-inventory') {
                const p = data.payload;
                pythonCode = `
import json
from renine.agents.inventory_agent import InventoryAgent
agent = InventoryAgent()
success = agent.delete_item(${JSON.stringify(p.name)})
print(json.dumps({'success': success}))
`;
            } else if (data.action === 'get-pets') {
                pythonCode = `
import json
from renine.agents.pet_agent import PetAgent
agent = PetAgent()
pets = [{'name': p.name, 'species': p.species, 'breed': p.breed, 'age': p.age, 'weight': p.weight, 'feeding_schedule': p.feeding_schedule, 'medical_conditions': p.medical_conditions, 'medications': p.medications, 'last_fed': p.last_fed.isoformat() if p.last_fed else None} for p in agent.list_pets()]
print(json.dumps(pets))
`;
            } else if (data.action === 'add-pet') {
                const p = data.payload;
                pythonCode = `
import json
from renine.agents.pet_agent import PetAgent
agent = PetAgent()
pet = agent.add_pet(
    name=${JSON.stringify(p.name)},
    species=${JSON.stringify(p.species)},
    breed=${JSON.stringify(p.breed)},
    age=float(${p.age}) if ${p.age !== null} else None,
    weight=float(${p.weight}) if ${p.weight !== null} else None,
    feeding_schedule=${JSON.stringify(p.feeding_schedule)},
    medical_conditions=${JSON.stringify(p.medical_conditions)},
    medications=${JSON.stringify(p.medications)}
)
print(json.dumps({'success': True, 'name': pet.name}))
`;
            } else if (data.action === 'delete-pet') {
                const p = data.payload;
                pythonCode = `
import json
from renine.agents.pet_agent import PetAgent
agent = PetAgent()
success = agent.delete_pet(${JSON.stringify(p.name)})
print(json.dumps({'success': success}))
`;
            } else if (data.action === 'get-people') {
                pythonCode = `
import json
from renine.memory.memory_manager import MemoryManager
mm = MemoryManager()
people = mm.list_people()
print(json.dumps(people))
`;
            } else if (data.action === 'add-person') {
                const p = data.payload;
                pythonCode = `
import json
from renine.memory.memory_manager import MemoryManager
mm = MemoryManager()
mm.store_person(
    name=${JSON.stringify(p.name)},
    relationship=${JSON.stringify(p.relationship)},
    age=int(${p.age}) if ${p.age !== null} else None,
    birthday=${JSON.stringify(p.birthday)},
    food_preferences=${JSON.stringify(p.food_preferences)},
    hobbies=${JSON.stringify(p.hobbies)},
    personality_traits=${JSON.stringify(p.personality_traits)},
    goals=${JSON.stringify(p.goals)},
    habits=${JSON.stringify(p.habits)},
    notes=${JSON.stringify(p.notes || '')}
)
print(json.dumps({'success': True, 'name': p.name}))
`;
            } else if (data.action === 'delete-person') {
                const p = data.payload;
                pythonCode = `
import json
from renine.memory.memory_manager import MemoryManager
mm = MemoryManager()
success = mm.delete_person(${JSON.stringify(p.name)})
print(json.dumps({'success': success}))
`;
            } else {
                throw new Error(`Unknown database action: ${data.action}`);
            }

            const result = await runPython(pythonCode);
            return result;
        } catch (error: any) {
            console.error('[IPC] Database action failed:', error);
            return { success: false, error: error.message };
        }
    });
}
