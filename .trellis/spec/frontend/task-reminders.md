# Task Reminder Indicator

## 1. Scope / Trigger

This contract applies to the authenticated app-shell task indicator backed by the background-task list and SSE snapshots. Use it when changing task status presentation, terminal-result acknowledgement, or the browser persistence key.

## 2. Signatures

The indicator consumes the existing `BackgroundTask` contract:

```ts
type BackgroundTaskStatus = 'queued' | 'running' | 'succeeded' | 'failed'

interface BackgroundTask {
  id: string
  status: BackgroundTaskStatus
}
```

No additional backend field or acknowledgement endpoint is required.

## 3. Contracts

- `queued`: no navigation reminder.
- `running`: show the number of running tasks, capped visually at `9+`; opening the log does not clear it.
- `succeeded`: when unread and no task is running, show the success indicator.
- `failed`: when unread and no task is running, show the failure indicator; failure takes precedence over success.
- Opening the task log acknowledges all currently loaded terminal tasks.
- Persist acknowledged terminal task IDs in `localStorage` under `mofeng-task-read:<userId>`.
- Do not show terminal reminders until the authenticated user ID is available.
- The button's accessible label must describe running, success, and failure states; color cannot be the only status signal.

## 4. Validation & Error Matrix

| Condition | Required behavior |
| --- | --- |
| Missing authenticated user ID | Hide terminal reminders and do not write acknowledgement state |
| Missing storage value | Treat all loaded terminal tasks as unread |
| Malformed storage JSON | Reset the in-memory acknowledged set and keep the task log usable |
| `localStorage.setItem` throws | Clear the reminder for the current session and still open the task log |
| Success and failure are both unread | Show failure |
| Running and terminal tasks coexist | Show the running count |

## 5. Good / Base / Bad Cases

- Good: a failed task shows a failure reminder, opening the log clears it, and a later terminal task shows a new reminder.
- Base: an empty list or a list containing only queued tasks shows no reminder.
- Bad: deriving unread state from `updated_at`; progress and log updates would repeatedly reactivate the reminder.

## 6. Tests Required

- Mount `AppShell` with queued and running tasks; assert only the running count is visible and remains after opening the log.
- Mount with unread success and failure tasks; assert failure precedence and acknowledgement persistence.
- Restore acknowledged IDs, add a later terminal task, and switch users; assert persistence and user isolation.
- Simulate malformed or unavailable storage; assert the task log still opens and the current-session reminder clears.
- Assert accessible labels for running, success, and failure states.

## 7. Wrong vs Correct

### Wrong

```ts
const hasReminder = computed(() => tasks.value.some((task) => task.updated_at > lastViewedAt))
```

This treats progress and log updates as new completion reminders.

### Correct

```ts
const unreadTerminalTasks = computed(() =>
  tasks.value.filter(
    (task) =>
      (task.status === 'succeeded' || task.status === 'failed') &&
      !viewedCompletedTaskIds.value.has(task.id),
  ),
)
```

Terminal task IDs give the acknowledgement state stable semantics across SSE updates.
