class RunbookLoader:

    def load(self, file_path: str):
        with open(file_path, "r", encoding="utf-8") as file:
            content = file.read()

        return {
            "file_path": file_path,
            "content": content
        }