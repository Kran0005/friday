import asyncio
from livekit.agents import AgentSession, RoomInputOptions
from livekit.plugins import noise_cancellation
from .agent import Assistant, get_agent_instructions
import threading


class FridayCore:
    def __init__(self):
        self.session = None
        self.loop = asyncio.new_event_loop()
        self.running = False
        self.ready = threading.Event()
        self.loop_thread = threading.Thread(target=self._start_loop, daemon=True)
        self.loop_thread.start()

    def _start_loop(self):
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self.start_session())
            if self.running:
                self.loop.run_forever()
        finally:
            pending = asyncio.all_tasks(self.loop)
            for task in pending:
                task.cancel()
            if pending:
                self.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            self.loop.close()

    async def start_session(self):
        try:
            self.session = AgentSession()
            await self.session.start(
                agent=Assistant(),
                room_input_options=RoomInputOptions(
                    video_enabled=False,
                    noise_cancellation=noise_cancellation.BVC(),
                )
            )
            print("[FridayCore] Session started successfully.")
            self.running = True
        except Exception as e:
            print(f"[FridayCore] Error starting session: {e}")
            self.running = False
        finally:
            self.ready.set()

    def ask(self, prompt: str) -> str:
        """Send a text turn to LiveKit and return the assistant's text reply."""
        if not self.ready.wait(timeout=30):
            return "Friday is still starting. Please try again in a moment."
        if not self.session or not self.running:
            return "Friday could not start its LiveKit session. Check the console and service credentials."

        async def inject_and_get():
            await self.session.current_agent.update_instructions(get_agent_instructions())
            run = self.session.run(user_input=prompt, input_modality="text")
            result = await asyncio.wait_for(run, timeout=45)
            responses = [
                event.item.text_content
                for event in result.events
                if event.type == "message"
                and event.item.role == "assistant"
                and event.item.text_content
            ]
            if responses:
                return "\n".join(responses)
            return "Friday finished the turn but returned no text. Check the LiveKit agent output."

        future = asyncio.run_coroutine_threadsafe(inject_and_get(), self.loop)
        try:
            return future.result(timeout=50)
        except TimeoutError:
            future.cancel()
            return "Friday did not receive a text reply in time. Check the Google API key and model availability."
        except Exception as e:
            future.cancel()
            return f"Friday couldn't complete that request: {e}"

    def stop(self):
        if self.loop.is_closed():
            return
        if self.loop.is_running():
            if self.session is not None:
                close_future = asyncio.run_coroutine_threadsafe(self.session.aclose(), self.loop)
                try:
                    close_future.result(timeout=5)
                except Exception as e:
                    print(f"[FridayCore] Session shutdown warning: {e}")
            self.loop.call_soon_threadsafe(self.loop.stop)
            if self.loop_thread is not threading.current_thread():
                self.loop_thread.join(timeout=5)
