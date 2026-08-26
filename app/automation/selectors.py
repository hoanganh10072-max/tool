LOGIN_INDICATORS = [
    "text=Quét mã QR",
    "text=Đăng nhập",
    "text=Login",
    "[data-id='qrcode']",
]

USER_ACTION_INDICATORS = [
    "text=/CAPTCHA/i",
    "text=/Xác minh bảo mật/i",
    "text=/Xác minh tài khoản/i",
    "text=/Verify your identity/i",
    "text=/Security check/i",
]

SEARCH_BUTTONS = [
    "[aria-label*='Tìm kiếm']",
    "[aria-label*='Search']",
    "button:has-text('Tìm kiếm')",
    "[data-id*='search']",
]

SEARCH_INPUTS = [
    "input[placeholder='Tìm kiếm']",
    "input[placeholder*='Tìm kiếm']",
    "input[placeholder*='Tìm bạn']",
    "input[placeholder*='Tìm bạn bè']",
    "input[placeholder*='Search']",
    "[role='searchbox']",
    "[contenteditable='true'][aria-label*='Tìm kiếm']",
]

ADD_FRIEND_BUTTONS = [
    "[aria-label*='Thêm bạn']",
    "[title*='Thêm bạn']",
    "[data-tooltip*='Thêm bạn']",
    "[data-title*='Thêm bạn']",
    "[aria-label*='Add friend']",
    "[title*='Add friend']",
    "[data-tooltip*='Add friend']",
    "[data-id*='addFriend']",
    "[data-id*='AddFriend']",
    "[data-id*='btn_AddFriend']",
    "[data-id*='friend_add']",
    "button:has-text('Thêm bạn')",
    "[role='button']:has-text('Thêm bạn')",
    "button:has-text('Add friend')",
    "[role='button']:has-text('Add friend')",
]

ADD_FRIEND_DIALOGS = [
    "text=/^Thêm bạn$/",
    "text=Thêm bạn bằng số điện thoại",
    "text=Nhập số điện thoại",
    "input[placeholder*='Số điện thoại']",
    "input[placeholder*='số điện thoại']",
    "input[placeholder*='phone']",
]

ADD_FRIEND_PHONE_INPUTS = [
    "input[placeholder='Số điện thoại']",
    "input[placeholder*='Số điện thoại']",
    "input[placeholder*='số điện thoại']",
    "input[placeholder*='Nhập số điện thoại']",
    "input[type='tel']",
    "input[inputmode='tel']",
    "input[autocomplete='tel']",
    "input[placeholder*='phone']",
    "input[placeholder*='Phone']",
]

ADD_FRIEND_SEARCH_BUTTONS = [
    "[id^='zl-modal'] [data-translate-inner='STR_SEARCH']:has-text('Tìm kiếm')",
    "[role='dialog'] [data-translate-inner='STR_SEARCH']:has-text('Tìm kiếm')",
    "[class*='modal' i] [data-translate-inner='STR_SEARCH']:has-text('Tìm kiếm')",
    "[id^='zl-modal'] button:has-text('Tìm kiếm')",
    "[id^='zl-modal'] [role='button']:has-text('Tìm kiếm')",
    "[role='dialog'] button:has-text('Tìm kiếm')",
    "[role='dialog'] [role='button']:has-text('Tìm kiếm')",
    "[class*='modal' i] button:has-text('Tìm kiếm')",
    "[class*='dialog' i] button:has-text('Tìm kiếm')",
    "[class*='popup' i] button:has-text('Tìm kiếm')",
    "[id^='zl-modal'] button:has-text('Search')",
    "[id^='zl-modal'] [role='button']:has-text('Search')",
    "[role='dialog'] button:has-text('Search')",
    "[role='dialog'] [role='button']:has-text('Search')",
]

ADD_FRIEND_NOT_FOUND_INDICATORS = [
    "text=Không tìm thấy tài khoản",
    "text=Không tìm thấy người dùng",
    "text=Không tìm thấy kết quả",
    "text=Không có kết quả",
    "text=Tài khoản không tồn tại",
    "text=Số điện thoại chưa đăng ký",
    "text=Số điện thoại không tồn tại",
    "text=Không tìm thấy",
    "text=No result",
    "text=No account found",
    "text=User not found",
]

ADD_FRIEND_ACCOUNT_MESSAGE_BUTTONS = [
    "[id^='zl-modal']:has-text('Thông tin tài khoản') [data-translate-inner='STR_CHAT']:has-text('Nhắn tin')",
    "[role='dialog']:has-text('Thông tin tài khoản') [data-translate-inner='STR_CHAT']:has-text('Nhắn tin')",
    "[class*='modal' i]:has-text('Thông tin tài khoản') [data-translate-inner='STR_CHAT']:has-text('Nhắn tin')",
    "[id^='zl-modal']:has-text('Thông tin tài khoản') button:has-text('Nhắn tin')",
    "[id^='zl-modal']:has-text('Thông tin tài khoản') [role='button']:has-text('Nhắn tin')",
    "[role='dialog']:has-text('Thông tin tài khoản') button:has-text('Nhắn tin')",
    "[role='dialog']:has-text('Thông tin tài khoản') [role='button']:has-text('Nhắn tin')",
    "[class*='modal' i]:has-text('Thông tin tài khoản') button:has-text('Nhắn tin')",
    "[class*='modal' i]:has-text('Thông tin tài khoản') [role='button']:has-text('Nhắn tin')",
    "[id^='zl-modal']:has-text('Account') button:has-text('Message')",
    "[id^='zl-modal']:has-text('Account') [role='button']:has-text('Message')",
]

ADD_FRIEND_MESSAGE_BUTTONS = [
    "[id^='zl-modal'] button:has-text('Nhắn tin')",
    "[id^='zl-modal'] [role='button']:has-text('Nhắn tin')",
    "[role='dialog'] button:has-text('Nhắn tin')",
    "[role='dialog'] [role='button']:has-text('Nhắn tin')",
    "[class*='modal' i] button:has-text('Nhắn tin')",
    "[class*='dialog' i] button:has-text('Nhắn tin')",
    "[class*='popup' i] button:has-text('Nhắn tin')",
    "[id^='zl-modal'] button:has-text('Message')",
    "[id^='zl-modal'] [role='button']:has-text('Message')",
]

PHONE_SEARCH_RESULT_TEXT = [
    "Tìm bạn qua số điện thoại",
    "Tìm kiếm bạn bè qua số điện thoại",
    "Find friends by phone",
    "Search by phone",
]

PHONE_RESULT_ROWS = [
    "[role='button']:has-text('{text}')",
    "[role='listitem']:has-text('{text}')",
    "li:has-text('{text}')",
    "[data-id]:has-text('{text}')",
]

CONTACT_RESULT_ROWS = [
    "[role='button']:has-text('{phone}')",
    "[role='listitem']:has-text('{phone}')",
    "li:has-text('{phone}')",
    "[data-id*='friend']:has-text('{phone}')",
    "[data-id*='contact']:has-text('{phone}')",
]

NOT_FOUND_INDICATORS = [
    "text=Không tìm thấy",
    "text=No result",
    "text=Không có kết quả",
    "text=Không tìm thấy kết quả",
]

CONTACT_NAME_CANDIDATES = [
    "[data-id='txt_Main_UserName']",
    "[data-id*='UserName']",
    "[data-id*='display_name']",
    "[class*='userName']",
    "[class*='displayName']",
]

CONVERSATION_PANE = [
    "[role='main']",
    "[data-id='conversation']",
    ".chat-view",
]

PROFILE_MESSAGE_BUTTONS = [
    "button:has-text('Nhắn tin')",
    "[role='button']:has-text('Nhắn tin')",
    "text=/^Nhắn tin$/",
    "button:has-text('Message')",
    "[role='button']:has-text('Message')",
]

MESSAGE_INPUTS = [
    "#input_line_0",
    "[id^='input_line_'][contenteditable='true']",
    "[data-id='richInput'] [contenteditable='true']",
    "[data-id*='richInput'] [contenteditable='true']",
    "[contenteditable='true'][placeholder*='Nhập @']",
    "[contenteditable='true'][aria-placeholder*='Nhập @']",
    "[contenteditable='true'][placeholder*='tin nhắn']",
    "[contenteditable='true'][aria-placeholder*='tin nhắn']",
    "[contenteditable='true'][aria-label*='Nhập tin nhắn']",
    "[contenteditable='true'][placeholder*='Nhập tin nhắn']",
    "[contenteditable='true'][aria-label*='tin nhắn']",
    "[contenteditable='true'][data-lexical-editor='true']",
    "[contenteditable='true'][role='textbox']",
    "textarea",
]

SEND_BUTTONS = [
    "[data-id='btn_Send']",
    "[data-id*='btn_Send']",
    "[aria-label*='Gửi']",
    "[aria-label*='Send']",
    "button:has-text('Gửi')",
    "button:has-text('Send')",
]

IMAGE_FILE_INPUTS = [
    "input[type='file'][accept*='image']",
    "input[type='file'][accept*='.jpg']",
    "input[type='file'][accept*='.png']",
    "input[type='file']",
]

IMAGE_UPLOAD_BUTTONS = [
    "[aria-label*='Ảnh']",
    "[title*='Ảnh']",
    "[data-title*='Ảnh']",
    "[data-tooltip*='Ảnh']",
    "[aria-label*='Hình']",
    "[title*='Hình']",
    "[aria-label*='Photo']",
    "[title*='Photo']",
    "[aria-label*='Image']",
    "[title*='Image']",
    "[data-id*='photo' i]",
    "[data-id*='image' i]",
    "[data-id*='picture' i]",
]

LOADING_INDICATORS = [
    "[aria-busy='true']",
    ".loading",
]
