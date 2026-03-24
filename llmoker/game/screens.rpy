################################################################################
## Initialization
################################################################################

init offset = -1

image llmoker_main_menu_video = Movie(
    play="gui/main.webm",
    channel="llmoker_main_menu_video",
    loop=True,
)

transform llmoker_main_menu_video_fit:
    xalign 0.5
    yalign 0.5
    xsize llmoker_gui_width
    ysize llmoker_gui_height

transform llmoker_neon_breathe:
    alpha 0.9
    linear 1.25 alpha 1.0
    linear 1.25 alpha 0.9
    repeat

transform llmoker_menu_fade_in:
    alpha 0.0
    linear 0.28 alpha 1.0

transform llmoker_menu_panel_slide_in:
    alpha 0.0
    xoffset -28
    pause 0.08
    easeout 0.32 alpha 1.0 xoffset 0

transform llmoker_menu_title_glow_in:
    alpha 0.0
    yoffset 18
    pause 0.18
    easeout 0.34 alpha 1.0 yoffset 0


################################################################################
## Styles
################################################################################

style default:
    properties gui.text_properties()
    language gui.language

style input:
    properties gui.text_properties("input", accent=True)
    adjust_spacing False

style hyperlink_text:
    properties gui.text_properties("hyperlink", accent=True)
    hover_underline True

style gui_text:
    properties gui.text_properties("interface")


style button:
    properties gui.button_properties("button")

style button_text is gui_text:
    properties gui.text_properties("button")
    yalign 0.5


style label_text is gui_text:
    properties gui.text_properties("label", accent=True)

style prompt_text is gui_text:
    properties gui.text_properties("prompt")


style bar:
    ysize gui.bar_size
    left_bar Frame("gui/bar/left.png", gui.bar_borders, tile=gui.bar_tile)
    right_bar Frame("gui/bar/right.png", gui.bar_borders, tile=gui.bar_tile)

style vbar:
    xsize gui.bar_size
    top_bar Frame("gui/bar/top.png", gui.vbar_borders, tile=gui.bar_tile)
    bottom_bar Frame("gui/bar/bottom.png", gui.vbar_borders, tile=gui.bar_tile)

style scrollbar:
    ysize gui.scrollbar_size
    base_bar Frame("gui/scrollbar/horizontal_[prefix_]bar.png", gui.scrollbar_borders, tile=gui.scrollbar_tile)
    thumb Frame("gui/scrollbar/horizontal_[prefix_]thumb.png", gui.scrollbar_borders, tile=gui.scrollbar_tile)

style vscrollbar:
    xsize gui.scrollbar_size
    base_bar Frame("gui/scrollbar/vertical_[prefix_]bar.png", gui.vscrollbar_borders, tile=gui.scrollbar_tile)
    thumb Frame("gui/scrollbar/vertical_[prefix_]thumb.png", gui.vscrollbar_borders, tile=gui.scrollbar_tile)

style slider:
    ysize gui.slider_size
    base_bar Frame("gui/slider/horizontal_[prefix_]bar.png", gui.slider_borders, tile=gui.slider_tile)
    thumb "gui/slider/horizontal_[prefix_]thumb.png"

style vslider:
    xsize gui.slider_size
    base_bar Frame("gui/slider/vertical_[prefix_]bar.png", gui.vslider_borders, tile=gui.slider_tile)
    thumb "gui/slider/vertical_[prefix_]thumb.png"


style frame:
    padding gui.frame_borders.padding
    background Frame("gui/frame.png", gui.frame_borders, tile=gui.frame_tile)



################################################################################
## In-game screens
################################################################################


## Say screen ##################################################################
##
## The say screen is used to display dialogue to the player. It takes two
## parameters, who and what, which are the name of the speaking character and
## the text to be displayed, respectively. (The who parameter can be None if no
## name is given.)
##
## This screen must create a text displayable with id "what", as Ren'Py uses
## this to manage text display. It can also create displayables with id "who"
## and id "window" to apply style properties.
##
## https://www.renpy.org/doc/html/screen_special.html#say

screen say(who, what):
    style_prefix "say"

    window:
        id "window"

        if who is not None:

            window:
                id "namebox"
                style "namebox"
                text who id "who"

        text what id "what"


    ## If there's a side image, display it above the text. Do not display on the
    ## phone variant - there's no room.
    if not renpy.variant("small"):
        add SideImage() xalign 0.0 yalign 1.0


## Make the namebox available for styling through the Character object.
init python:
    config.character_id_prefixes.append('namebox')

style window is default
style say_label is default
style say_dialogue is default
style say_thought is say_dialogue

style namebox is default
style namebox_label is say_label


style window:
    xalign 0.5
    xmaximum gui_scale(972)
    yalign 1.0
    ysize gui.textbox_height
    left_padding gui_scale(28)
    right_padding gui_scale(28)
    top_padding gui_scale(14)
    bottom_padding gui_scale(16)
    background "#06080dcf"

style namebox:
    xpos gui.name_xpos
    xanchor gui.name_xalign
    xsize gui.namebox_width
    ypos gui.name_ypos
    ysize gui.namebox_height
    left_padding gui_scale(12)
    right_padding gui_scale(12)
    top_padding gui_scale(5)
    bottom_padding gui_scale(5)
    background "#09172be8"

style say_label:
    properties gui.text_properties("name", accent=True)
    color "#27a7ff"
    xalign gui.name_xalign
    yalign 0.5
    outlines [(1, "#07111d", 0, 0)]

style say_dialogue:
    properties gui.text_properties("dialogue")
    xpos gui.dialogue_xpos
    xsize gui.dialogue_width
    ypos gui.dialogue_ypos
    adjust_spacing False
    outlines [(1, "#04070d", 0, 0)]

## Input screen ################################################################
##
## This screen is used to display renpy.input. The prompt parameter is used to
## pass a text prompt in.
##
## This screen must create an input displayable with id "input" to accept the
## various input parameters.
##
## https://www.renpy.org/doc/html/screen_special.html#input

screen input(prompt):
    style_prefix "input"

    window:

        vbox:
            xanchor gui.dialogue_text_xalign
            xpos gui.dialogue_xpos
            xsize gui.dialogue_width
            ypos gui.dialogue_ypos

            text prompt style "input_prompt"
            input id "input"

style input_prompt is default

style input_prompt:
    xalign gui.dialogue_text_xalign
    properties gui.text_properties("input_prompt")

style input:
    xalign gui.dialogue_text_xalign
    xmaximum gui.dialogue_width


## Choice screen ###############################################################
##
## This screen is used to display the in-game choices presented by the menu
## statement. The one parameter, items, is a list of objects, each with caption
## and action fields.
##
## https://www.renpy.org/doc/html/screen_special.html#choice

screen choice(items):
    style_prefix "choice"

    vbox:
        for i in items:
            textbutton i.caption action i.action


style choice_vbox is vbox
style choice_button is button
style choice_button_text is button_text

style choice_vbox:
    xalign 0.5
    ypos 405
    yanchor 0.5

    spacing gui.choice_spacing

style choice_button is default:
    properties gui.button_properties("choice_button")

style choice_button_text is default:
    properties gui.text_properties("choice_button")


## Quick Menu screen ###########################################################
##
## The quick menu is displayed in-game to provide easy access to the out-of-game
## menus.

screen quick_menu():

    ## Ensure this appears on top of other screens.
    zorder 100

    if quick_menu:

        hbox:
            style_prefix "quick"

            xalign 0.5
            yalign 1.0

            textbutton "뒤로" action Rollback()
            textbutton "기록" action ShowMenu('history')
            textbutton "건너뛰기" action Skip() alternate Skip(fast=True, confirm=True)
            textbutton "자동" action Preference("auto-forward", "toggle")
            textbutton "저장" action ShowMenu('save')
            textbutton "빠른 저장" action QuickSave()
            textbutton "빠른 불러오기" action QuickLoad()
            textbutton "환경 설정" action ShowMenu('preferences')


## This code ensures that the quick_menu screen is displayed in-game, whenever
## the player has not explicitly hidden the interface.
init python:
    config.overlay_screens.append("quick_menu")

default quick_menu = True

style quick_button is default
style quick_button_text is button_text

style quick_button:
    properties gui.button_properties("quick_button")

style quick_button_text:
    properties gui.text_properties("quick_button")


################################################################################
## Main and Game Menu Screens
################################################################################

## Navigation screen ###########################################################
##
## This screen is included in the main and game menus, and provides navigation
## to other menus, and to start the game.

screen navigation():

    vbox:
        style_prefix "navigation"

        xpos gui.navigation_xpos
        yalign 0.5

        spacing gui_scale(10)

        if main_menu:

            textbutton "시작" action Start()

        else:

            textbutton "기록" action ShowMenu("history")

            textbutton "저장" action ShowMenu("save")

        textbutton "불러오기" action ShowMenu("load")

        textbutton "환경 설정" action ShowMenu("preferences")

        if _in_replay:

            textbutton "리플레이 종료" action EndReplay(confirm=True)

        elif not main_menu:

            textbutton "메인 메뉴" action MainMenu()

        textbutton "정보" action ShowMenu("about")

        if renpy.variant("pc") or (renpy.variant("web") and not renpy.variant("mobile")):

            ## Help isn't necessary or relevant to mobile devices.
            textbutton "도움말" action ShowMenu("help")

        if renpy.variant("pc"):

            ## The quit button is banned on iOS and unnecessary on Android and
            ## Web.
            textbutton "종료" action Quit(confirm=not main_menu)


style navigation_button is gui_button
style navigation_button_text is gui_button_text

style navigation_button:
    size_group "navigation"
    properties gui.button_properties("navigation_button")
    xminimum gui_scale(286)
    left_padding gui_scale(22)
    right_padding gui_scale(18)
    top_padding gui_scale(11)
    bottom_padding gui_scale(11)
    background "#08131ed8"
    hover_background "#18304ae8"

style navigation_button_text:
    properties gui.text_properties("navigation_button")
    font "fonts/malgunbd.ttf"
    size gui_scale(24)
    color "#e7f3ff"
    hover_color "#ffffff"
    outlines [(1, "#071019", 0, 0)]


## Main Menu screen ############################################################
##
## Used to display the main menu when Ren'Py starts.
##
## https://www.renpy.org/doc/html/screen_special.html#main-menu

screen main_menu():

    ## This ensures that any other menu screen is replaced.
    tag menu
    on "show" action Function(play_main_menu_music)

    add "llmoker_main_menu_video" at llmoker_main_menu_video_fit
    add Solid("#02020601")

    ## This empty frame darkens the main menu.
    frame:
        style "main_menu_frame"
        at llmoker_menu_panel_slide_in

    frame:
        style "main_menu_brand_plate"
        at llmoker_menu_title_glow_in

    ## The use statement includes another screen inside this one. The actual
    ## contents of the main menu are in the navigation screen.
    fixed:
        at llmoker_menu_panel_slide_in
        use navigation

    if gui.show_name:

        fixed:
            style "main_menu_brand_panel"
            at llmoker_menu_title_glow_in

            text "[config.name!t]":
                style "main_menu_title_glow"
                at llmoker_neon_breathe

            text "[config.name!t]":
                style "main_menu_title"


style main_menu_frame is empty
style main_menu_text is gui_text
style main_menu_title is main_menu_text
style main_menu_title_glow is main_menu_text
style main_menu_version is main_menu_text
style main_menu_brand_panel is empty
style main_menu_brand_plate is empty

style main_menu_frame:
    xsize gui_scale(300)
    yfill True
    background "#04101ab6"

style main_menu_brand_panel:
    xpos gui_scale(402)
    ypos gui_scale(36)
    xmaximum gui_scale(280)
    ymaximum gui_scale(92)

style main_menu_brand_plate:
    xpos gui_scale(374)
    ypos gui_scale(20)
    xsize gui_scale(330)
    ysize gui_scale(96)
    background "#1808185a"

style main_menu_text:
    properties gui.text_properties("main_menu", accent=True)

style main_menu_title:
    font "fonts/malgunbd.ttf"
    size gui_scale(50)
    color "#fff9fd"
    outlines [(1, "#2c0918", 0, 0), (2, "#ff67b422", 0, 0), (4, "#ff3fa914", 0, 0)]

style main_menu_title_glow:
    font "fonts/malgunbd.ttf"
    size gui_scale(50)
    color "#ff76cf"
    outlines [(2, "#ff4bb648", 0, 0), (4, "#ff4bb626", 0, 0), (7, "#ff4bb612", 0, 0)]


## Game Menu screen ############################################################
##
## This lays out the basic common structure of a game menu screen. It's called
## with the screen title, and displays the background, title, and navigation.
##
## The scroll parameter can be None, or one of "viewport" or "vpgrid".
## This screen is intended to be used with one or more children, which are
## transcluded (placed) inside it.

screen game_menu(title, scroll=None, yinitial=0.0, spacing=0):

    style_prefix "game_menu"

    if main_menu:
        add "llmoker_main_menu_video" at llmoker_main_menu_video_fit
    else:
        add gui.game_menu_background

    key "K_ESCAPE" action (ShowMenu("main_menu") if main_menu else Return())
    key "game_menu" action (ShowMenu("main_menu") if main_menu else Return())

    frame:
        style "game_menu_modal_frame"
        at llmoker_menu_fade_in

        vbox:
            spacing gui_scale(16)

            hbox:
                xfill True
                spacing gui_scale(14)

                text title:
                    style "game_menu_modal_title"

                null width gui_scale(12)

                textbutton "돌아가기":
                    style "game_menu_modal_close_button"
                    action (ShowMenu("main_menu") if main_menu else Return())

            add Solid("#ff67c53f") xsize gui_scale(240) ysize gui_scale(2)

            if scroll == "viewport":

                viewport:
                    yinitial yinitial
                    scrollbars "vertical"
                    mousewheel True
                    draggable True
                    pagekeys True

                    side_yfill True

                    vbox:
                        spacing spacing

                        transclude

            elif scroll == "vpgrid":

                vpgrid:
                    cols 1
                    yinitial yinitial

                    scrollbars "vertical"
                    mousewheel True
                    draggable True
                    pagekeys True

                    side_yfill True

                    spacing spacing

                    transclude

            else:

                transclude


style game_menu_outer_frame is empty
style game_menu_navigation_frame is empty
style game_menu_content_frame is empty
style game_menu_viewport is gui_viewport
style game_menu_side is gui_side
style game_menu_scrollbar is gui_vscrollbar

style game_menu_label is gui_label
style game_menu_label_text is gui_label_text

style return_button is navigation_button
style return_button_text is navigation_button_text

style game_menu_modal_frame is empty
style game_menu_modal_title is gui_label_text
style game_menu_modal_close_button is navigation_button
style game_menu_modal_close_button_text is navigation_button_text

style game_menu_modal_frame:
    xalign 0.5
    yalign 0.5
    xmaximum gui_scale(860)
    ymaximum gui_scale(520)
    padding (gui_scale(28), gui_scale(22))
    background "#07111bef"

style game_menu_modal_title:
    font "fonts/malgunbd.ttf"
    size gui_scale(30)
    color "#f5f8ff"
    outlines [(1, "#071019", 0, 0)]

style game_menu_modal_close_button:
    xalign 1.0
    xminimum gui_scale(138)
    left_padding gui_scale(16)
    right_padding gui_scale(16)
    top_padding gui_scale(10)
    bottom_padding gui_scale(10)
    background "#0f1727e8"
    hover_background "#1f2d42f0"

style game_menu_modal_close_button_text:
    font "fonts/malgunbd.ttf"
    size gui_scale(22)
    color "#f0f6ff"
    hover_color "#ffffff"
    outlines [(1, "#071019", 0, 0)]

style game_menu_viewport:
    xsize gui_scale(1380)

style game_menu_vscrollbar:
    unscrollable gui.unscrollable

style game_menu_side:
    spacing gui_scale(12)

style game_menu_label:
    xpos gui_scale(75)
    ysize gui_scale(150)

style game_menu_label_text:
    size gui_scale(40)
    color gui.accent_color
    yalign 0.5

style return_button:
    xpos gui.navigation_xpos
    yalign 1.0
    yoffset -gui_scale(45)


## About screen ################################################################
##
## This screen gives credit and copyright information about the game and Ren'Py.
##
## There's nothing special about this screen, and hence it also serves as an
## example of how to make a custom screen.

screen about():

    tag menu

    ## This use statement includes the game_menu screen inside this one. The
    ## vbox child is then included inside the viewport inside the game_menu
    ## screen.
    use game_menu("정보", scroll="viewport"):

        style_prefix "about"

        vbox:
            label "[config.name!t]"
            text "버전 [config.version!t]\n"
            text "카지노 테이블, 로컬 LLM NPC, 저장/회고 구조를 결합한 포커 게임입니다.\n"
            text "대사, 판단, 기억, 연출은 모두 게임 내부 구조로 연결됩니다."


style about_label is gui_label
style about_label_text is gui_label_text
style about_text is gui_text

style about_label_text:
    size gui.label_text_size


## Load and Save screens #######################################################
##
## These screens are responsible for letting the player save the game and load
## it again. Since they share nearly everything in common, both are implemented
## in terms of a third screen, file_slots.
##
## https://www.renpy.org/doc/html/screen_special.html#save https://
## www.renpy.org/doc/html/screen_special.html#load

screen save():

    tag menu

    use file_slots("저장")


screen load():

    tag menu

    use file_slots("불러오기")


screen file_slots(title):

    default page_name_value = FilePageNameInputValue(pattern=("페이지 {}"), auto=("자동 저장"), quick=("빠른 저장"))

    use game_menu(title):

        fixed:

            ## This ensures the input will get the enter event before any of the
            ## buttons do.
            order_reverse True

            ## The page name, which can be edited by clicking on a button.
            button:
                style "page_label"

                key_events True
                xalign 0.5
                action page_name_value.Toggle()

                input:
                    style "page_label_text"
                    value page_name_value

            ## The grid of file slots.
            grid gui.file_slot_cols gui.file_slot_rows:
                style_prefix "slot"

                xalign 0.5
                yalign 0.5

                spacing gui.slot_spacing

                for i in range(gui.file_slot_cols * gui.file_slot_rows):

                    $ slot = i + 1

                    button:
                        action FileAction(slot)

                        has vbox

                        add FileScreenshot(slot) xalign 0.5

                        text FileTime(slot, format=("{#file_time}%Y-%m-%d %H:%M"), empty=("빈 슬롯")):
                            style "slot_time_text"

                        text FileSaveName(slot):
                            style "slot_name_text"

                        key "save_delete" action FileDelete(slot)

            ## Buttons to access other pages.
            vbox:
                style_prefix "page"

                xalign 0.5
                yalign 1.0

                hbox:
                    xalign 0.5

                    spacing gui.page_spacing

                    textbutton "이전" action FilePagePrevious()

                    if config.has_autosave:
                        textbutton "자동" action FilePage("auto")

                    if config.has_quicksave:
                        textbutton "빠른 저장" action FilePage("quick")

                    ## range(1, 10) gives the numbers from 1 to 9.
                    for page in range(1, 10):
                        textbutton "[page]" action FilePage(page)

                    textbutton "다음" action FilePageNext()

                if config.has_sync:
                    if CurrentScreenName() == "save":
                        textbutton "동기화 업로드":
                            action UploadSync()
                            xalign 0.5
                    else:
                        textbutton "동기화 다운로드":
                            action DownloadSync()
                            xalign 0.5


style page_label is gui_label
style page_label_text is gui_label_text
style page_button is gui_button
style page_button_text is gui_button_text

style slot_button is gui_button
style slot_button_text is gui_button_text
style slot_time_text is slot_button_text
style slot_name_text is slot_button_text

style page_label:
    xpadding 75
    ypadding 5

style page_label_text:
    textalign 0.5
    layout "subtitle"
    hover_color gui.hover_color

style page_button:
    properties gui.button_properties("page_button")

style page_button_text:
    properties gui.text_properties("page_button")

style slot_button:
    properties gui.button_properties("slot_button")

style slot_button_text:
    properties gui.text_properties("slot_button")


## Preferences screen ##########################################################
##
## The preferences screen allows the player to configure the game to better suit
## themselves.
##
## https://www.renpy.org/doc/html/screen_special.html#preferences

screen preferences():

    tag menu

    use game_menu("환경 설정", scroll="viewport"):

        vbox:
            spacing 18

            text "이 화면은 LLMoker 플레이 감각을 조정하는 전용 설정만 제공한다." size gui_scale(20) color "#f3f3f3" font "fonts/malgun.ttf" xmaximum gui_scale(800)

            vbox:
                spacing 10
                text "플레이" size gui_scale(24) color "#ffe8a3" font "fonts/malgunbd.ttf"

                hbox:
                    spacing 18
                    text "텍스트 속도" size gui_scale(19) color "#f3f3f3" font "fonts/malgunbd.ttf" xsize gui_scale(180)
                    bar value Preference("text speed") xsize gui_scale(420)

                hbox:
                    spacing 18
                    text "자동 진행 지연" size gui_scale(19) color "#f3f3f3" font "fonts/malgunbd.ttf" xsize gui_scale(180)
                    bar value Preference("auto-forward time") xsize gui_scale(420)

                hbox:
                    spacing 12
                    textbutton "자동 진행 켜기/끄기" action Preference("auto-forward", "toggle")
                    textbutton "퀵 메뉴 표시/숨김" action SetVariable("quick_menu", not quick_menu)

            vbox:
                spacing 10
                text "오디오" size gui_scale(24) color "#ffe8a3" font "fonts/malgunbd.ttf"

                hbox:
                    spacing 18
                    text "배경 음악" size gui_scale(19) color "#f3f3f3" font "fonts/malgunbd.ttf" xsize gui_scale(180)
                    bar value Preference("music volume") xsize gui_scale(420)

                hbox:
                    spacing 18
                    text "효과음" size gui_scale(19) color "#f3f3f3" font "fonts/malgunbd.ttf" xsize gui_scale(180)
                    bar value Preference("sound volume") xsize gui_scale(420)

            vbox:
                spacing 10
                text "상대 AI" size gui_scale(24) color "#ffe8a3" font "fonts/malgunbd.ttf"
                text "현재 선택: [store.poker_bot_mode == 'llm_npc' and 'LLM NPC' or '스크립트봇']" size gui_scale(19) color "#f3f3f3" font "fonts/malgun.ttf"
                hbox:
                    spacing 12
                    textbutton "LLM NPC 사용" action Function(apply_poker_bot_mode, "llm_npc")
                    textbutton "스크립트봇 사용" action Function(apply_poker_bot_mode, "script_bot")

            text "게임 흐름, 대사 반응, 저장 구조에 영향을 주는 항목만 이 화면에서 다룬다." size gui_scale(18) color "#c7d8ff" font "fonts/malgun.ttf" xmaximum gui_scale(800)


style pref_label is gui_label
style pref_label_text is gui_label_text
style pref_vbox is vbox

style radio_label is pref_label
style radio_label_text is pref_label_text
style radio_button is gui_button
style radio_button_text is gui_button_text
style radio_vbox is pref_vbox

style check_label is pref_label
style check_label_text is pref_label_text
style check_button is gui_button
style check_button_text is gui_button_text
style check_vbox is pref_vbox

style slider_label is pref_label
style slider_label_text is pref_label_text
style slider_slider is gui_slider
style slider_button is gui_button
style slider_button_text is gui_button_text
style slider_pref_vbox is pref_vbox

style mute_all_button is check_button
style mute_all_button_text is check_button_text

style pref_label:
    top_margin gui.pref_spacing
    bottom_margin 3

style pref_label_text:
    yalign 1.0

style pref_vbox:
    xsize 760

style radio_vbox:
    spacing gui.pref_button_spacing

style radio_button:
    properties gui.button_properties("radio_button")
    foreground "gui/button/radio_[prefix_]foreground.png"

style radio_button_text:
    properties gui.text_properties("radio_button")

style check_vbox:
    spacing gui.pref_button_spacing

style check_button:
    properties gui.button_properties("check_button")
    foreground "gui/button/check_[prefix_]foreground.png"

style check_button_text:
    properties gui.text_properties("check_button")

style slider_slider:
    xsize 525

style slider_button:
    properties gui.button_properties("slider_button")
    yalign 0.5
    left_margin 15

style slider_button_text:
    properties gui.text_properties("slider_button")

style slider_vbox:
    xsize 760


## History screen ##############################################################
##
## This is a screen that displays the dialogue history to the player. While
## there isn't anything special about this screen, it does have to access the
## dialogue history stored in _history_list.
##
## https://www.renpy.org/doc/html/history.html

screen history():

    tag menu

    ## Avoid predicting this screen, as it can be very large.
    predict False

    use game_menu("기록", scroll=("vpgrid" if gui.history_height else "viewport"), yinitial=1.0, spacing=gui.history_spacing):

        style_prefix "history"

        for h in _history_list:

            window:

                ## This lays things out properly if history_height is None.
                has fixed:
                    yfit True

                if h.who:

                    label h.who:
                        style "history_name"
                        substitute False

                        ## Take the color of the who text from the Character, if
                        ## set.
                        if "color" in h.who_args:
                            text_color h.who_args["color"]

                $ what = renpy.filter_text_tags(h.what, allow=gui.history_allow_tags)
                text what:
                    substitute False

        if not _history_list:
            label "대화 기록이 비어 있습니다."


## This determines what tags are allowed to be displayed on the history screen.

define gui.history_allow_tags = { "alt", "noalt", "rt", "rb", "art" }


style history_window is empty

style history_name is gui_label
style history_name_text is gui_label_text
style history_text is gui_text

style history_label is gui_label
style history_label_text is gui_label_text

style history_window:
    xfill True
    ysize gui.history_height

style history_name:
    xpos gui.history_name_xpos
    xanchor gui.history_name_xalign
    ypos gui.history_name_ypos
    xsize gui.history_name_width

style history_name_text:
    min_width gui.history_name_width
    textalign gui.history_name_xalign

style history_text:
    xpos gui.history_text_xpos
    ypos gui.history_text_ypos
    xanchor gui.history_text_xalign
    xsize gui.history_text_width
    min_width gui.history_text_width
    textalign gui.history_text_xalign
    layout ("subtitle" if gui.history_text_xalign else "tex")

style history_label:
    xfill True

style history_label_text:
    xalign 0.5


## Help screen #################################################################
##
## A screen that gives information about key and mouse bindings. It uses other
## screens (keyboard_help, mouse_help, and gamepad_help) to display the actual
## help.

screen help():

    tag menu

    use game_menu("도움말", scroll="viewport"):

        style_prefix "help"

        vbox:
            spacing 18

            text "LLMoker 기본 조작" size gui_scale(30) color "#ffffff" font "fonts/malgunbd.ttf"

            vbox:
                spacing 8
                text "테이블 진행" size gui_scale(24) color "#ffe8a3" font "fonts/malgunbd.ttf"
                text "Enter, Space, 마우스 클릭으로 대사를 넘긴다." size gui_scale(19) color "#f3f3f3" font "fonts/malgun.ttf" xmaximum gui_scale(760)
                text "메인 메뉴에서는 왼쪽 내비게이션, 게임 중에는 하단 도크를 사용한다." size gui_scale(19) color "#f3f3f3" font "fonts/malgun.ttf" xmaximum gui_scale(760)

            vbox:
                spacing 8
                text "행동 선택" size gui_scale(24) color "#ffe8a3" font "fonts/malgunbd.ttf"
                text "베팅 단계에서는 체크, 베팅, 콜, 레이즈, 폴드를 선택한다." size gui_scale(19) color "#f3f3f3" font "fonts/malgun.ttf" xmaximum gui_scale(760)
                text "드로우 단계에서는 교체할 카드를 누른 뒤 교체 확정을 누른다." size gui_scale(19) color "#f3f3f3" font "fonts/malgun.ttf" xmaximum gui_scale(760)

            vbox:
                spacing 8
                text "화면 전환" size gui_scale(24) color "#ffe8a3" font "fonts/malgunbd.ttf"
                text "Esc 또는 우측 시스템 도크의 메인 메뉴 버튼으로 게임 메뉴를 연다." size gui_scale(19) color "#f3f3f3" font "fonts/malgun.ttf" xmaximum gui_scale(760)
                text "로그 보기, 저장, 불러오기, 환경 설정은 시스템 도크에서 연다." size gui_scale(19) color "#f3f3f3" font "fonts/malgun.ttf" xmaximum gui_scale(760)


style help_button is gui_button
style help_button_text is gui_button_text
style help_label is gui_label
style help_label_text is gui_label_text
style help_text is gui_text

style help_button:
    properties gui.button_properties("help_button")
    xmargin 12

style help_button_text:
    properties gui.text_properties("help_button")

style help_label:
    xsize 375
    right_padding 30

style help_label_text:
    size gui.text_size
    xalign 1.0
    textalign 1.0



################################################################################
## Additional screens
################################################################################


## Confirm screen ##############################################################
##
## The confirm screen is called when Ren'Py wants to ask the player a yes or no
## question.
##
## https://www.renpy.org/doc/html/screen_special.html#confirm

screen confirm(message, yes_action, no_action):

    ## Ensure other screens do not get input while this screen is displayed.
    modal True

    zorder 200

    style_prefix "confirm"

    add "gui/overlay/confirm.png"

    frame:

        vbox:
            xalign .5
            yalign .5
            spacing 45

            label _(message):
                style "confirm_prompt"
                xalign 0.5

            hbox:
                xalign 0.5
                spacing 150

                textbutton "예" action yes_action
                textbutton "아니오" action no_action

    ## Right-click and escape answer "no".
    key "game_menu" action no_action


style confirm_frame is gui_frame
style confirm_prompt is gui_prompt
style confirm_prompt_text is gui_prompt_text
style confirm_button is gui_medium_button
style confirm_button_text is gui_medium_button_text

style confirm_frame:
    background Frame([ "gui/confirm_frame.png", "gui/frame.png"], gui.confirm_frame_borders, tile=gui.frame_tile)
    padding gui.confirm_frame_borders.padding
    xalign .5
    yalign .5

style confirm_prompt_text:
    textalign 0.5
    layout "subtitle"

style confirm_button:
    properties gui.button_properties("confirm_button")

style confirm_button_text:
    properties gui.text_properties("confirm_button")


## Skip indicator screen #######################################################
##
## The skip_indicator screen is displayed to indicate that skipping is in
## progress.
##
## https://www.renpy.org/doc/html/screen_special.html#skip-indicator

screen skip_indicator():

    zorder 100
    style_prefix "skip"

    frame:

        hbox:
            spacing 9

            text "건너뛰는 중"

            text "▸" at delayed_blink(0.0, 1.0) style "skip_triangle"
            text "▸" at delayed_blink(0.2, 1.0) style "skip_triangle"
            text "▸" at delayed_blink(0.4, 1.0) style "skip_triangle"


## This transform is used to blink the arrows one after another.
transform delayed_blink(delay, cycle):
    alpha .5

    pause delay

    block:
        linear .2 alpha 1.0
        pause .2
        linear .2 alpha 0.5
        pause (cycle - .4)
        repeat


style skip_frame is empty
style skip_text is gui_text
style skip_triangle is skip_text

style skip_frame:
    ypos gui.skip_ypos
    background Frame("gui/skip.png", gui.skip_frame_borders, tile=gui.frame_tile)
    padding gui.skip_frame_borders.padding

style skip_text:
    size gui.notify_text_size

style skip_triangle:
    ## We have to use a font that has the BLACK RIGHT-POINTING SMALL TRIANGLE
    ## glyph in it.
    font "DejaVuSans.ttf"


## Notify screen ###############################################################
##
## The notify screen is used to show the player a message. (For example, when
## the game is quicksaved or a screenshot has been taken.)
##
## https://www.renpy.org/doc/html/screen_special.html#notify-screen

screen notify(message):

    zorder 100
    style_prefix "notify"

    frame at notify_appear:
        text "[message!tq]"

    timer 3.25 action Hide('notify')


transform notify_appear:
    on show:
        alpha 0
        linear .25 alpha 1.0
    on hide:
        linear .5 alpha 0.0


style notify_frame is empty
style notify_text is gui_text

style notify_frame:
    ypos gui.notify_ypos

    background Frame("gui/notify.png", gui.notify_frame_borders, tile=gui.frame_tile)
    padding gui.notify_frame_borders.padding

style notify_text:
    properties gui.text_properties("notify")


## NVL screen ##################################################################
##
## This screen is used for NVL-mode dialogue and menus.
##
## https://www.renpy.org/doc/html/screen_special.html#nvl


screen nvl(dialogue, items=None):

    window:
        style "nvl_window"

        has vbox:
            spacing gui.nvl_spacing

        ## Displays dialogue in either a vpgrid or the vbox.
        if gui.nvl_height:

            vpgrid:
                cols 1
                yinitial 1.0

                use nvl_dialogue(dialogue)

        else:

            use nvl_dialogue(dialogue)

        ## Displays the menu, if given. The menu may be displayed incorrectly if
        ## config.narrator_menu is set to True.
        for i in items:

            textbutton i.caption:
                action i.action
                style "nvl_button"

    add SideImage() xalign 0.0 yalign 1.0


screen nvl_dialogue(dialogue):

    for d in dialogue:

        window:
            id d.window_id

            fixed:
                yfit gui.nvl_height is None

                if d.who is not None:

                    text d.who:
                        id d.who_id

                text d.what:
                    id d.what_id


## This controls the maximum number of NVL-mode entries that can be displayed at
## once.
define config.nvl_list_length = gui.nvl_list_length

style nvl_window is default
style nvl_entry is default

style nvl_label is say_label
style nvl_dialogue is say_dialogue

style nvl_button is button
style nvl_button_text is button_text

style nvl_window:
    xfill True
    yfill True

    background "gui/nvl.png"
    padding gui.nvl_borders.padding

style nvl_entry:
    xfill True
    ysize gui.nvl_height

style nvl_label:
    xpos gui.nvl_name_xpos
    xanchor gui.nvl_name_xalign
    ypos gui.nvl_name_ypos
    yanchor 0.0
    xsize gui.nvl_name_width
    min_width gui.nvl_name_width
    textalign gui.nvl_name_xalign

style nvl_dialogue:
    xpos gui.nvl_text_xpos
    xanchor gui.nvl_text_xalign
    ypos gui.nvl_text_ypos
    xsize gui.nvl_text_width
    min_width gui.nvl_text_width
    textalign gui.nvl_text_xalign
    layout ("subtitle" if gui.nvl_text_xalign else "tex")

style nvl_thought:
    xpos gui.nvl_thought_xpos
    xanchor gui.nvl_thought_xalign
    ypos gui.nvl_thought_ypos
    xsize gui.nvl_thought_width
    min_width gui.nvl_thought_width
    textalign gui.nvl_thought_xalign
    layout ("subtitle" if gui.nvl_text_xalign else "tex")

style nvl_button:
    properties gui.button_properties("nvl_button")
    xpos gui.nvl_button_xpos
    xanchor gui.nvl_button_xalign

style nvl_button_text:
    properties gui.text_properties("nvl_button")


## Bubble screen ###############################################################
##
## The bubble screen is used to display dialogue to the player when using speech
## bubbles. The bubble screen takes the same parameters as the say screen, must
## create a displayable with the id of "what", and can create displayables with
## the "namebox", "who", and "window" ids.
##
## https://www.renpy.org/doc/html/bubble.html#bubble-screen

screen bubble(who, what):
    style_prefix "bubble"

    window:
        id "window"

        if who is not None:

            window:
                id "namebox"
                style "bubble_namebox"

                text who:
                    id "who"

        text what:
            id "what"

style bubble_window is empty
style bubble_namebox is empty
style bubble_who is default
style bubble_what is default

style bubble_window:
    xpadding 30
    top_padding 5
    bottom_padding 5

style bubble_namebox:
    xalign 0.5

style bubble_who:
    xalign 0.5
    textalign 0.5
    color "#000"

style bubble_what:
    align (0.5, 0.5)
    text_align 0.5
    layout "subtitle"
    color "#000"

define bubble.frame = Frame("gui/bubble.png", 55, 55, 55, 95)
define bubble.thoughtframe = Frame("gui/thoughtbubble.png", 55, 55, 55, 55)

define bubble.properties = {
    "bottom_left" : {
        "window_background" : Transform(bubble.frame, xzoom=1, yzoom=1),
        "window_bottom_padding" : 27,
    },

    "bottom_right" : {
        "window_background" : Transform(bubble.frame, xzoom=-1, yzoom=1),
        "window_bottom_padding" : 27,
    },

    "top_left" : {
        "window_background" : Transform(bubble.frame, xzoom=1, yzoom=-1),
        "window_top_padding" : 27,
    },

    "top_right" : {
        "window_background" : Transform(bubble.frame, xzoom=-1, yzoom=-1),
        "window_top_padding" : 27,
    },

    "thought" : {
        "window_background" : bubble.thoughtframe,
    }
}

define bubble.expand_area = {
    "bottom_left" : (0, 0, 0, 22),
    "bottom_right" : (0, 0, 0, 22),
    "top_left" : (0, 22, 0, 0),
    "top_right" : (0, 22, 0, 0),
    "thought" : (0, 0, 0, 0),
}



################################################################################
## Mobile Variants
################################################################################

style pref_vbox:
    variant "medium"
    xsize 675

## Since a mouse may not be present, we replace the quick menu with a version
## that uses fewer and bigger buttons that are easier to touch.
screen quick_menu():
    variant "touch"

    zorder 100

    if quick_menu:

        hbox:
            style_prefix "quick"

            xalign 0.5
            yalign 1.0

            textbutton "뒤로" action Rollback()
            textbutton "건너뛰기" action Skip() alternate Skip(fast=True, confirm=True)
            textbutton "자동" action Preference("auto-forward", "toggle")
            textbutton "메뉴" action ShowMenu()


style window:
    variant "small"
    background "gui/phone/textbox.png"

style radio_button:
    variant "small"
    foreground "gui/phone/button/radio_[prefix_]foreground.png"

style check_button:
    variant "small"
    foreground "gui/phone/button/check_[prefix_]foreground.png"

style nvl_window:
    variant "small"
    background "gui/phone/nvl.png"

style main_menu_frame:
    variant "small"
    background "gui/phone/overlay/main_menu.png"

style game_menu_outer_frame:
    variant "small"
    background "gui/phone/overlay/game_menu.png"

style game_menu_navigation_frame:
    variant "small"
    xsize 510

style game_menu_content_frame:
    variant "small"
    top_margin 0

style pref_vbox:
    variant "small"
    xsize 600

style bar:
    variant "small"
    ysize gui.bar_size
    left_bar Frame("gui/phone/bar/left.png", gui.bar_borders, tile=gui.bar_tile)
    right_bar Frame("gui/phone/bar/right.png", gui.bar_borders, tile=gui.bar_tile)

style vbar:
    variant "small"
    xsize gui.bar_size
    top_bar Frame("gui/phone/bar/top.png", gui.vbar_borders, tile=gui.bar_tile)
    bottom_bar Frame("gui/phone/bar/bottom.png", gui.vbar_borders, tile=gui.bar_tile)

style scrollbar:
    variant "small"
    ysize gui.scrollbar_size
    base_bar Frame("gui/phone/scrollbar/horizontal_[prefix_]bar.png", gui.scrollbar_borders, tile=gui.scrollbar_tile)
    thumb Frame("gui/phone/scrollbar/horizontal_[prefix_]thumb.png", gui.scrollbar_borders, tile=gui.scrollbar_tile)

style vscrollbar:
    variant "small"
    xsize gui.scrollbar_size
    base_bar Frame("gui/phone/scrollbar/vertical_[prefix_]bar.png", gui.vscrollbar_borders, tile=gui.scrollbar_tile)
    thumb Frame("gui/phone/scrollbar/vertical_[prefix_]thumb.png", gui.vscrollbar_borders, tile=gui.scrollbar_tile)

style slider:
    variant "small"
    ysize gui.slider_size
    base_bar Frame("gui/phone/slider/horizontal_[prefix_]bar.png", gui.slider_borders, tile=gui.slider_tile)
    thumb "gui/phone/slider/horizontal_[prefix_]thumb.png"

style vslider:
    variant "small"
    xsize gui.slider_size
    base_bar Frame("gui/phone/slider/vertical_[prefix_]bar.png", gui.vslider_borders, tile=gui.slider_tile)
    thumb "gui/phone/slider/vertical_[prefix_]thumb.png"

style slider_vbox:
    variant "small"
    xsize None

style slider_slider:
    variant "small"
    xsize 900
