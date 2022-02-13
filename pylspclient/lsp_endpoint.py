from __future__ import print_function
import asyncio
from concurrent.futures import ThreadPoolExecutor, Future
import threading
import collections
from typing import Any
from pylspclient import lsp_structs

class LspEndpoint(threading.Thread):
    def __init__(self, json_rpc_endpoint, loop:asyncio.AbstractEventLoop, method_callbacks={}, notify_callbacks={}, timeout=5):
        threading.Thread.__init__(self)
        self.json_rpc_endpoint = json_rpc_endpoint
        self.notify_callbacks = notify_callbacks
        self.method_callbacks = method_callbacks
        self.event_dict = {}
        self.response_dict = {}
        self._futures_dict: dict[Any, Future] = {}
        self._loop = loop
        self.next_id = 0
        self._timeout = timeout
        self.shutdown_flag = False

    def handle_result(self, rpc_id, result, error):
        print('got result from', rpc_id, repr(result)[:50], repr(error)[:50])
        fut = self._futures_dict[rpc_id]

        if error:
            fut.set_exception(lsp_structs.ResponseError(error.get("code"), error.get("message"), error.get("data")))
            print('error on ', rpc_id)
        else:
            fut.set_result(result)
            print('set on ', rpc_id)

    def stop(self):
        self.shutdown_flag = True

    def run(self):
        while not self.shutdown_flag:
            try:
                jsonrpc_message = self.json_rpc_endpoint.recv_response()
                if jsonrpc_message is None:
                    print("server quit")
                    break
                method = jsonrpc_message.get("method")
                result = jsonrpc_message.get("result")
                error = jsonrpc_message.get("error")
                rpc_id = jsonrpc_message.get("id")
                params = jsonrpc_message.get("params")

                if method:
                    if rpc_id:
                        # a call for method
                        if method not in self.method_callbacks:
                            raise lsp_structs.ResponseError(lsp_structs.ErrorCodes.MethodNotFound, "Method not found: {method}".format(method=method))
                        result = self.method_callbacks[method](params)
                        self.send_response(rpc_id, result, None)
                    else:
                        # a call for notify
                        if method not in self.notify_callbacks:
                            # Have nothing to do with this.
                            print("Notify method not found: {method}.".format(method=method))
                        else:
                            self.notify_callbacks[method](params)
                else:
                    self.handle_result(rpc_id, result, error)
            except lsp_structs.ResponseError as e:
                print('oh merde', e)
                self.send_response(rpc_id, None, e)


    async def send_response(self, id, result, error):
        message_dict = {}
        message_dict["jsonrpc"] = "2.0"
        message_dict["id"] = id
        if result:
            message_dict["result"] = result
        if error:
            message_dict["error"] = error
        return await self.json_rpc_endpoint.send_request(message_dict)


    def send_message(self, method_name, params, id = None):
        message_dict = {}
        message_dict["jsonrpc"] = "2.0"
        if id is not None:
            message_dict["id"] = id
        message_dict["method"] = method_name
        message_dict["params"] = params
        return self.json_rpc_endpoint.send_request(message_dict)

    async def call_method(self, method_name:str, **kwargs) -> Any:
        current_id = self.next_id
        self.next_id += 1
        fut = self._futures_dict[current_id] = self._loop.create_future()
        if self.shutdown_flag:
            return None
        self.send_message(method_name, kwargs, current_id)
        cb = None
        if cb:
          fut.add_done_callback(cb)
        return asyncio.wrap_future(fut)

    def old_call_method(self, method_name:str, **kwargs) -> None:
        current_id = self.next_id
        self.next_id += 1
        cond = threading.Condition()
        self.event_dict[current_id] = cond
        self._futures_dict[current_id] = self._loop.create_future()

        cond.acquire()
        print('call method', method_name, current_id)
        self.send_message(method_name, kwargs, current_id)
        if self.shutdown_flag:
            return None

        if not 'init' in method_name:
            return cond.release()

        if not cond.wait(timeout=self._timeout):
            raise TimeoutError()
        cond.release()

        self.event_dict.pop(current_id, None)
        result, error = self.response_dict.pop(current_id)
        if error:
            raise lsp_structs.ResponseError(error.get("code"), error.get("message"), error.get("data"))
        return result


    def send_notification(self, method_name, **kwargs):
        self.send_message(method_name, kwargs)
