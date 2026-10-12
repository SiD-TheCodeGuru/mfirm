import flet as ft

def main(page: ft.Page):
    print("Page initialized successfully!")
    page.add(ft.Text("Hello Mushroom ERP", size=30))
    page.update()

if __name__ == "__main__":
    print("Launching test window...")
    # Test 1: Try browser mode first to bypass desktop window issues
    ft.run(main, view=ft.AppView.WEB_BROWSER)