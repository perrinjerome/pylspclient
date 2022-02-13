from asyncio import get_event_loop
from concurrent.futures import ThreadPoolExecutor
import pathlib
import pylspclient
import subprocess
import threading
import sys
import time

capabilities = {
    'textDocument': {
        'codeAction': {
            'dynamicRegistration': True
        },
        'codeLens': {
            'dynamicRegistration': True
        },
        'colorProvider': {
            'dynamicRegistration': True
        },
        'completion': {
            'completionItem': {
                'commitCharactersSupport': True,
                'documentationFormat': ['markdown', 'plaintext'],
                'snippetSupport': True
            },
            'completionItemKind': {
                'valueSet': [
                    1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17,
                    18, 19, 20, 21, 22, 23, 24, 25
                ]
            },
            'contextSupport': True,
            'dynamicRegistration': True
        },
        'definition': {
            'dynamicRegistration': True
        },
        'documentHighlight': {
            'dynamicRegistration': True
        },
        'documentLink': {
            'dynamicRegistration': True
        },
        'documentSymbol': {
            'dynamicRegistration': True,
            'symbolKind': {
                'valueSet': [
                    1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17,
                    18, 19, 20, 21, 22, 23, 24, 25, 26
                ]
            }
        },
        'formatting': {
            'dynamicRegistration': True
        },
        'hover': {
            'contentFormat': ['markdown', 'plaintext'],
            'dynamicRegistration': True
        },
        'implementation': {
            'dynamicRegistration': True
        },
        'onTypeFormatting': {
            'dynamicRegistration': True
        },
        'publishDiagnostics': {
            'relatedInformation': True
        },
        'rangeFormatting': {
            'dynamicRegistration': True
        },
        'references': {
            'dynamicRegistration': True
        },
        'rename': {
            'dynamicRegistration': True
        },
        'signatureHelp': {
            'dynamicRegistration': True,
            'signatureInformation': {
                'documentationFormat': ['markdown', 'plaintext']
            }
        },
        'synchronization': {
            'didSave': True,
            'dynamicRegistration': True,
            'willSave': True,
            'willSaveWaitUntil': True
        },
        'typeDefinition': {
            'dynamicRegistration': True
        }
    },
    'workspace': {
        'applyEdit': True,
        'configuration': True,
        'didChangeConfiguration': {
            'dynamicRegistration': True
        },
        'didChangeWatchedFiles': {
            'dynamicRegistration': True
        },
        'executeCommand': {
            'dynamicRegistration': True
        },
        'symbol': {
            'dynamicRegistration': True,
            'symbolKind': {
                'valueSet': [
                    1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17,
                    18, 19, 20, 21, 22, 23, 24, 25, 26
                ]
            }
        },
        'workspaceEdit': {
            'documentChanges': True
        },
        'workspaceFolders': True
    }
}


class ReadPipe(threading.Thread):

    def __init__(self, pipe):
        threading.Thread.__init__(self)
        self.pipe = pipe

    def run(self):
        line = self.pipe.readline().decode('utf-8')
        while line:
            print(f"got err: {line}", end='', file=sys.stderr, flush=True)
            line = self.pipe.readline().decode('utf-8')


async def main():
    buildoutls_cmd = [
        #'/usr/bin/script', '-q', 'buildoutls.script', 
        sys.executable, "-m", "buildoutls", "--logfile", "bls.log"
    ]
    p = subprocess.Popen(buildoutls_cmd,
                         stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
    read_pipe = ReadPipe(p.stderr)
    read_pipe.start()
    json_rpc_endpoint = pylspclient.JsonRpcEndpoint(p.stdin, p.stdout)
    # To work with socket: sock_fd = sock.makefile()
    diags = []

    def publish_diags(m):
        print(f'diagnostics: {len(m["diagnostics"])} diag')
        diags.append(m)

    notify_callbacks = {'textDocument/publishDiagnostics': publish_diags}
    tpe = ThreadPoolExecutor()
    lsp_endpoint = pylspclient.LspEndpoint(
        json_rpc_endpoint,
        asyncio.get_event_loop(),
        notify_callbacks=notify_callbacks,
    )

    lsp_client = pylspclient.LspClient(lsp_endpoint)

    root_path = (pathlib.Path(".") / "slapos").absolute()
    if not root_path.exists():
        raise ValueError('Error: please git clone https://lab.nexedi.com/nexedi/slapos.git here')

    workspace_folders = [{'name': 'slapos', 'uri': root_path.as_uri()}]
    # XXX do we need workspace folders here ?
    print(await lsp_client.initialize(p.pid, None, root_path.as_uri(), None,
                                      capabilities, "off", workspace_folders))
    print(await lsp_client.initialized())

    fname = root_path / 'component/python3/buildout.cfg'
    uri = fname.as_uri()
    languageId = 'zc-buildout'
    version = 1

    with open(fname) as f:
        text = f.read()

    await lsp_client.didOpen(
        pylspclient.lsp_structs.TextDocumentItem(uri, languageId, version,
                                                 text))
    try:
        symbols = await lsp_client.documentSymbol(
            pylspclient.lsp_structs.TextDocumentIdentifier(uri))
        print(symbols)
    except pylspclient.lsp_structs.ResponseError:
        # documentSymbol is supported from version 8.
        print("Failed to document symbols")

    pos = pylspclient.lsp_structs.Position(1, 3)
    textDoc = pylspclient.lsp_structs.TextDocumentIdentifier(uri)
    completionContext = pylspclient.lsp_structs.CompletionContext(
        pylspclient.lsp_structs.CompletionTriggerKind.Invoked)

    import itertools
    version_counter = itertools.count()
    
    import random

    r = random.Random("seed")

    while True:
        version = next(version_counter)
        delay = r.random() * .1
        await asyncio.sleep(delay)
        await lsp_client.didChange(
            pylspclient.lsp_structs.TextDocumentItem(
                uri,
                languageId,
                version,
                text,
            ),
            [{
                "range": {
                    "start": {
                        "line": 19,
                        "character": 0
                    },
                    "end": {
                        "line": 19,
                        "character": 0
                    }
                },
                "rangeLength": 0,
                "text": "a"
            }],
        )
        completion_request_id = lsp_endpoint.next_id
        t = asyncio.create_task(
            lsp_client.completion(textDoc, pos, completionContext))
        lsp_endpoint.send_notification(
            '$/cancelRequest',
            id=completion_request_id,
        )

        a, b = await asyncio.gather(
            t,
            lsp_client.completion(textDoc, pos, completionContext),
            return_exceptions=True,
        )

        from pprint import pprint
        pprint((a, b))

        if not completion_request_id % 30:
            import pdb
            pdb.set_trace()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
