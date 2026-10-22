# RunSpriteRun Help


RunSpriteRun is a free Windows program for making and testing sprite animations inside the colour limits of classic computers and consoles. This guide covers every part of the program: the windows, the tools, the menus and the keys.

## What RunSpriteRun does

You bring in your sprites, the program fits them to the colours of the system you picked, and you put the frames in order, group them into animations, and **run** them with the keyboard to see how a character will move. When you are happy, you save the project and export PNG sprite sheets and single frames.

- **Works offline.** One project is open at a time, and nothing is sent anywhere.
- **Eight systems.** Sega Genesis / Mega Drive, Super Nintendo (SNES), Atari ST, Atari STE, Amiga, Apple IIgs, Commodore 64 and Apple II (Double Hi-Res). Each keeps your colours inside that system's rules.
- **Up to 120 frames** of 4 x 4 to 128 x 128 pixels, and up to 32 animation groups.
- **Edit mode** for drawing and fixing pixels, with three layers.
- **Edit menu tools** to shrink a sprite or reduce its number of colours.

## Who it is for

Anyone who makes or tests pixel-art sprites: retro game developers, pixel artists, and fans who want to see how a sprite behaves with a particular system's palette. You do not need to know how to program.

## 2. Getting started

### Installing

RunSpriteRun runs on Windows 10 and 11 (64-bit). It works fully offline: it never connects to the internet and sends nothing anywhere.

1. Go to the project's Releases page on GitHub and download **RunSpriteRun_Setup_v2.0.9.exe** (or the newest version listed).
2. Double-click the file and follow the Setup wizard. No other software, such as Python, is needed.
3. Start RunSpriteRun from the Start menu.

The program installs for your own Windows user (in AppData\Local\Programs), so it does not ask for administrator rights. Your projects are kept in a **Projects** folder, and a set of ready-made examples is installed in **Examples\Projects**.

### Your first minute

1. When the program opens, the **Start Project** box appears. Give the project a name, choose a target system, choose a frame size and press **Create Project** (see section 3).
2. The main window opens with your frames along the bottom.
3. Click a frame in the timeline to look at it, press **Play** in the Frame Group Preview to see a group animate, or press a key that has a group to try the sprite with the keyboard.
4. Press **Ctrl+S** to save.

Tip: to look around before making anything, press **Open Project** in the Start Project box and open one of the examples.

### The window at a glance

- **Menu bar** (top): File, Edit, Group, Help and About.
- **Frame view** (top left): the selected frame, enlarged, with a pixel grid. This is where you draw in Edit mode.
- **Frame Group Preview** (middle): plays a group of frames on a loop.
- **RunSpriteRun window** (right): the live test. Use the keys to control the sprite, and press Esc to stop.
- **Palette and colour editor** (top right): the project's colours and the tools to change them.
- **Set Frame Group panel**: where groups of frames are defined; its Set Rules button opens Frame Group Control, where keys are given to groups.
- **Timeline and frames** (bottom): every frame in order, with a key pad picture at its left end.

The three sprite views always have a black background and enlarge the sprite in whole-number steps only, with no smoothing, so you see exactly the pixels you will get.

## 3. Starting a project

A project is made in the **Start Project** box. It opens when the program starts, and again with **File > New Project** (Ctrl+N). The box also has an **Open Project** button for projects you already have.

### Project name and target system

- **Project name**: 1 to 40 characters, using letters, numbers, a hyphen and an underscore. No spaces.
- **Target system**: the retro machine whose colour limits the project follows. It is chosen here and cannot be changed later. A **System details** panel shows the system's maximum sprite colours, bits per channel, colour depth and total colours.

| System | Max sprite colours | Colour depth | Colours the system can show |
|---|---|---|---|
| Sega Genesis / Mega Drive | 16 | 9-bit (RGB 3:3:3) | 512 |
| Super Nintendo (SNES) | 16 | 15-bit (RGB 5:5:5) | 32,768 |
| Atari ST | 16 | 9-bit (RGB 3:3:3) | 512 |
| Atari STE | 32 | 12-bit (RGB 4:4:4) | 4,096 |
| Amiga | 32 | 12-bit (RGB 4:4:4) | 4,096 |
| Commodore 64 | 16 | 16 fixed colours | 16 |
| Apple II Double Hi-Res | 16 | 16 fixed colours | 16 |
| Apple IIgs | 16 | 12-bit (RGB 4:4:4) | 4,096 |

The maximum sprite colours include the transparent colour. The Commodore 64 and Apple II Double Hi-Res have a fixed palette: you pick from their set colours, and the colour editor and Reduce Palette are switched off for them.

### Frame size and speed

- **Set frame size**: type a Width and Height, each from 4 to 128 pixels (it starts at 32 x 32).
- **Set from imported sprites**: takes the size from the files or sprite sheet you chose, and shows it beside the button.
- **Frames per second**: 3, 6, 12 or 24 (default 12). You can change this later in File > Settings.

### Starting sprites

Three choices, which you can switch between freely:

- **Blank project**: 1 to 120 empty frames (default 12), filled with the transparent colour and named Frame_1, Frame_2 and so on.
- **Import sprite sheet**: start from one filled-in sprite sheet (see "Importing a sprite sheet" below).
- **Import image files**: choose up to 120 PNG, BMP or GIF files from one folder.

A line under the buttons says what will be created. If something blocks **Create Project**, it is shown there in orange.

### Importing image files

The files become frames in natural file-name order (frame2 comes before frame10). Each one is checked:

- More than 120 files rejects the whole import.
- Width and height must match the frame size, otherwise the file is rejected.
- Transparency (an alpha channel with see-through pixels) is not supported. Use a solid colour for the transparent parts, and set it as the transparent colour.
- Every pixel is snapped to the nearest colour the system can show. If any pixel changed, you are told, and the file is still imported.
- The colours in the project plus the file's colours must not exceed the system's maximum. A file that would go over is skipped. Files are processed in order, so earlier files get the colours first.

A message lists any skipped files and the reason. Your original files are never changed. Animated GIFs are not supported.

If the frame size you set is larger than the sprites, each sprite is centred on the bigger canvas and the extra area is filled with the transparent colour. A size smaller than the sprites is refused; nothing is cropped.

### Importing a sprite sheet

A project can start from one sprite sheet, only here and only once. The sheet should follow the layout of the program's own **blank sprite sheet** (section 9), which is also the layout of every sheet the program saves or exports.

- The program finds the boxes from lines in the **Box colour** (default bright green #00FF00). All boxes must be the same size, 4 to 128 pixels each way.
- The inside of each box becomes a frame. A box that is entirely the **Transparent colour** (default magenta #FF00FF) is treated as empty and left out.
- The two colours must be different. If the sheet needs more colours than the system allows, the whole sheet is refused.
- On the first Save, a copy of the original sheet is placed in the project folder. The original is never changed.

### Create Project

Press **Create Project** to open the main window. A new project's transparent colour is magenta (#FF00FF) unless the imported sheet says otherwise.

## 4. The timeline and frames

The **Timeline and frames** panel runs along the bottom of the window and shows every frame as a strip of thumbnails. An animation is a list of frames played one after another, each for the same time, set by the project's frames per second. There is no tweening or fading: when one frame's time ends, the next replaces it instantly.

### Reading the timeline

- Eight frames are visible at once; a project can hold up to **120 frames**.
- Under each thumbnail are the **frame number** (its position, set automatically), the **frame label** (editable) and the **frame group** it belongs to (read-only here).
- Pixels in the transparent colour are not drawn in the thumbnails, so the black background shows through.
- Scroll with the scroll bar, the large arrow buttons at either end (one frame per click), or the mouse wheel. The strip keeps the selected frame in view.
- On the left is the **key pad**, a picture of a controller that lights up the keys you hold while RunSpriteRun is running (section 5).

### Selecting frames

- Click a frame to select it. It appears in the Frame view.
- **Ctrl+click** adds a frame to the selection, or removes it.
- **Shift+click** selects the range from the first frame you clicked to the one you clicked now.
- A plain click goes back to a single frame.

Selected frames show a blue tint and a blue border; the main frame has a thin white line inside it. Ctrl+click and Shift+click work once the timeline has the focus (click a frame first). Selecting several frames is not available in Edit mode.

You can also pick a frame from the **Frame number** or **Frame label** lists above the Frame view, or step through frames with the previous and next triangle buttons.

### Frame labels

Every label is a name, an underscore and a three-digit number, for example **Idle_004**.

- You edit the **name** (1 to 60 characters: letters, numbers, a hyphen and an underscore, no spaces).
- The **number** is the frame's position, shown as fixed text. It updates by itself whenever frames are added, moved or removed.
- If the frame is in a group, renaming it renames the whole group's frames. Each frame keeps its own number.
- Labels are used in file names when you save and export.

### Reordering frames

Drag a frame left or right, or press **Ctrl+Left** / **Ctrl+Right** to move the selected frame one place. A marker shows where it will land. Press Esc or drop it outside the strip to cancel. Moving several selected frames at once is not available.

### Copying and pasting frames

- Select one or more frames and press **Ctrl+C**, then **Ctrl+V**. A small window asks whether to paste **Before the first copied frame** or **After the last copied frame**.
- Or right-click a frame and choose **Copy before** or **Copy after** to put a copy next to it straight away. On a frame inside a multiple selection, this copies the whole selection.
- A copy keeps its name, takes its position number, and joins the group of the frame it sits next to.
- The 120-frame limit is checked before anything is pasted.

Ctrl+C and Ctrl+V work only while the timeline has the focus and you are not typing a label.

### Deleting frames

Select the frames and press **Delete**. The program asks you to confirm and reminds you that you can undo. A group keeps its remaining frames; a group left with none is deleted, and the question says so. At least one frame must remain.

### Adding frames

New frames are added in Edit mode (section 7), as a copy of an existing frame or as an empty frame, before or after the current frame or as frame 1.

### Undo and redo

Reordering, label changes, group changes, deleting and pasting are all undoable with **Ctrl+Z** and **Ctrl+Y** (or the Edit menu).

## 5. Frame groups and running animations

A **frame group** is a named run of frames that can be played, and assigned to a key. Groups are how you build things like Walk, Jump and Idle, and how you test them with the keyboard.

### The three views

- **Frame view** (top left): the selected frame, enlarged, with a pixel grid. It does not play. In Edit mode it becomes the drawing surface.
- **Frame Group Preview** (middle): choose a group from its list and press **Play** to loop it. The back and forward triangles step through the group's frames. It ignores keys.
- **RunSpriteRun window** (right): the live test. Press a key that has a group to start it, and **Esc** to stop it. Its **Scale** toggle switches between the whole-number zoom and actual size (one sprite pixel = one screen pixel), and **Zoom -** / **Zoom +** change the size.

### Making a group

In the **Set Frame Group** panel:

1. Choose **New group** in the list beside the panel title (or use **Group > New Group**, Ctrl+G).
2. Type a **Name**: 1 to 20 characters, unique in the project, letters, numbers, a hyphen and an underscore, no spaces.
3. Choose a **Colour**. It becomes the border colour of the group's frames in the timeline.
4. Choose the **From** and **To** frames. A group is a continuous run, and can be a single frame.
5. **Press Set Rules to choose which keys play the group and what happens when they are let go (see Frame Group Control, below)**.
6. Press **Apply**.

A frame belongs to at most one group, and groups cannot overlap. If the range includes a frame that is already in another group, Apply is refused, and the message offers **Copy into new group**, which copies those frames to the end of the timeline and makes the group from the copies. A project can hold up to 32 groups.

To edit a group, pick it from the list (or click one of its frames), change it and press Apply. Renaming a group updates any rule that pointed to it. **Group > Delete Group** removes a group after confirmation; its frames stay in the timeline.

### Keys: On Hold

**A group's own key is set in the Frame Group Control window, in the Group keys rows under the rules (see below)**. While the key is held in RunSpriteRun, the group loops.

- Single keys: **W, A, S, D** and **1 to 6** (the top row or the number pad).
- Diagonals: **W+A** (up-left), **W+D** (up-right), **S+D** (down-right) and **S+A** (down-left). A diagonal is two direction keys held together, and has its own group like any key. If it has a group, it plays when both keys are held, whichever went down first.
- **None**: the group has no key (useful for a resting loop that other groups go to).

Each key belongs to one group. If you choose a key that is already used, the program asks whether to move it.

### Resting state: On Release

The **On Release** rule, also set in the Frame Group Control window, says what the sprite does when the key is let go:

- **Go To Frame**: show a chosen frame and hold it until the next key press.
- **Go to Group**: play another group (tick **Loop** to repeat it, or leave it off to show its first frame as a still). A rule can point at its own group, such as an Idle group that loops on itself.

A new group starts with Go To Frame 1. If a frame is moved, a rule that points to it follows. If a group a rule points to is deleted, the program lists the rules affected.

### Frame Group Control: key rules

The Set Rules button in the Set Frame Group panel (or Group > Frame Group Control) opens the Frame Group Control window. It works like the controller of a console game: it says which keys, held alone or together, play which group. The window stays open beside the main window, so you can keep it open while you run the animation. It is greyed out in Edit mode.

The top of the window shows the controller of your system: eight directions (W, A, S, D and the four diagonals) and its fire buttons. The Atari ST, Atari STE, Amiga, Commodore 64, Apple II and Apple IIgs have 1 button (key 1), the Sega Genesis / Mega Drive has 3 (keys 1 to 3), and the SNES has 6 (keys 1 to 4 and the L and R shoulder buttons, which are keys 5 and 6). The keys you hold while RunSpriteRun is running light up on the picture.

To make a rule:

1. Press + Add rule. A small box asks for the keys. Click every key that must be held together (for example W, D and 1) and press OK. The new rule goes to the top of the list.
2. Choose the group that plays. The list holds the groups you have already made.
3. Choose Loop (the group repeats while the keys are held) or Play once (it plays through one time).
4. Under "When all keys are released", choose what happens when you let go: the group's own On Release rule (the default), Go To Frame, or Go to Group (Loop, Play once, or First frame only). Play once plays the group one time and then that group's own release choice applies.

How the rules work:

- **The top rule wins.** Rules are checked from the top and the first rule whose keys are all held plays. Put the more specific rules higher: W+D+1 above W+D above D. Use the up and down arrows to move a rule, and the cross to delete it.
- **Play once** plays the group one time and will not play it again until you let go of the keys. Then the next matching rule, or the group of the newest key you are holding, takes over. For example: hold D (Walk right), then press A. A rule D+A that plays TurnLeft once shows the turn, and then Walk left starts.
- **Adding a key to a chord** works too. While W+D is held, pressing 1 as well switches to a W+D+1 rule (for example a shot), and letting go of 1 returns to the W+D group.
- **Group keys.** Under the rules, one row for each group that has a key of its own. They apply after your rules: a diagonal beats a single key, otherwise the key pressed last wins. You can change a group's key, and its release choice (Stay on the last frame, Go To Frame or Go to Group), in these rows. A key that your system's controller does not have is marked "not on this system's controller", but still works.
- **Changing groups.** If you rename a group, its rules follow. If you delete a group, or delete frames that leave it empty, the rules that play it are removed and the program lists them first.

Every change in the window is applied at once and can be undone with Ctrl+Z. Apply, Esc and the X in the title bar all just close the window. The rules are saved in the project, and Save and Export also write them as text and JSON files (see Saving and Export).

**Making a turn: Only if in.** Each rule has an "Only if in" button under its keys (the default is Any frame). Click it and tick one or more groups: the rule fires only if the frame on screen is in one of them. Ticking several groups lets one rule depend on every 'facing right' group, for example. The program has no setting for which way a character faces: it looks at the frame it is showing. This is how you make a character turn before it walks the other way.

Example, for a character with the groups WalkLeft, WalkRight and TurnLeft. A is left and D is right. Set these rules from the top:

1. A, Only if in WalkRight: play TurnLeft, Play once. When all keys are released: Go To Frame, a frame inside WalkLeft.
2. D, Any frame: play WalkRight, Loop. When all keys are released: Go To Frame, a frame inside WalkRight.
3. A, Any frame: play WalkLeft, Loop. When all keys are released: Go To Frame, a frame inside WalkLeft.

Hold D and Hercules walks right; let go and he stands. Press A and the left turn plays once, then he walks left. Press A again while already facing left and he walks straight away, because he is no longer showing a WalkRight frame. Keep the turn rule above the plain A rule, or the turn never plays. Each walk group's release frame must lie inside that group, otherwise the program thinks the character is facing the wrong way. For a turn the other way, add a TurnRight group and a rule D, Only if in WalkLeft, above rule 2. A turn can also be set as a Transition (below), which needs no extra rule.

If you rename a group, the Only if in lists follow it. If you delete a group, a rule that plays it is removed, and the group is taken out of every Only if in list (a rule whose list becomes empty is removed). The program lists these first.

**Opposite keys.** A joystick cannot press opposite directions together, so neither can the keyboard here. W and S, and A and D, are never counted together and cannot be chosen for a rule or a group key (the opposite key is greyed out in the Keys held box). While you hold A, pressing D does nothing; if you let go of A while still holding D, D starts counting as a normal key. You can add W or S to A or D to make a diagonal.

**Transitions.** Under the rules is a Transitions section: going FROM one group, several groups or Any group, TO a group, play a transition group ONCE first. The transition group has no key of its own. For example, going from WalkRight to WalkLeft plays TurnLeft once, then WalkLeft. A row that names the from-groups beats an Any row. Starts count too (Idle to Walk). Transitions apply when a key press changes the group; stops use the group's release choice (Go to Group, play once). Tick 'Can be interrupted' if a new key press should cut a transition short; by default it finishes first.

**Action animations (7, 8, 9, 0).** Some animations are not played by the controller but by the game, for example a death when a character touches a spike. Keys 7, 8, 9 and 0 let you test them. They are shown apart, in amber, under the 1 to 6 buttons on the key pad and in Frame Group Control, and work on every system. Set them up like any rule: Add rule, choose the amber 7, 8, 9 or 0 in the Keys held box, choose the group, Loop or Play once, and what happens on release (for example Play once, then Go To Frame on the last frame so the last frame stays). An action key stands alone: it cannot be combined with any other key, and while it is held the controller keys are ignored.

### Running the animation

1. Press a key that has a group. RunSpriteRun starts and shows frame 1 until a key plays its group.
2. Hold a key that has a group. That group loops, from its first frame, for as long as you hold it.
3. Release the key. The On Release rule applies at once.
4. Press Esc to stop and go back to the start state.

Frame Group Control rules are checked first, from the top. If no rule matches and several keys are held, the most recently pressed key's group plays. When you let it go, the most recent key still held takes over. Keys with no group do nothing. Pressing a key that has a group while RunSpriteRun is stopped starts it. Keys work only while RunSpriteRun is running and no text box has focus. Changing the frame order, labels or groups while running stops it.

The **key pad** at the left of the timeline lights up the keys you are holding, in each group's colour (muted green if the group has no colour). Under the 1 to 6 buttons an amber row, ACTION ANIMATIONS, shows keys 7, 8, 9 and 0 (see Action animations under Frame Group Control).

### Timing

Every frame is shown for the same time, set by **Frames per second** (3, 6, 12 or 24). Change it any time in **File > Settings**.

## 6. Palette and colour editor

The card at the top right holds the project's palette and the tools to change it. Everything here follows the target system: you can only choose colours the system can actually display.

### The palette

- The palette has exactly as many slots as the system's maximum sprite colours (16 or 32). Used slots show a colour; free slots are blank with their slot number.
- The title shows the counts, for example "9 used, 7 free of 16".
- It lists the colours used in the frames, in order of first appearance. A colour that no frame uses any more stays in the palette, in its slot, and still counts toward the colour limit, until you delete it (right-click it and choose Delete colour) or reduce the palette.

### Replacing a colour

1. Choose a new colour with the **R, G and B sliders** (each has - and + buttons that move it one level), the colour square, or the **Hex box**.
2. Click a palette square to overwrite that colour.

Every pixel of the old colour in every frame changes to the new one. After the click the colour is no longer armed, so choose a colour again before the next replacement. The square the next click will use is outlined in yellow.

The sliders and colour square snap to colours the system can display. The **Hex box** shows the colour as #RRGGBB, is editable, snaps to the nearest valid colour, and rejects anything that is not six hex digits. If you choose a colour that is already in the palette, the program asks "Merge these colours?", and merging frees a slot.

The SNES colour square shows a stepped subset of its colours; the sliders and Hex box still reach all of them.

### Adding a colour

The + button, between the transparent colour box and the eyedropper, adds a new colour to the next free slot. In Edit mode the + CLR tool does exactly the same. Both are greyed out when the palette is full, and on the Commodore 64 and Apple II Double Hi-Res, whose colours are fixed.

1. Click +. It is highlighted, the next free palette square is outlined in yellow, and everything else in the program is locked. The eyedropper is switched on for you.
2. Choose the colour with the R, G and B sliders, the colour square, the Hex box, or the eyedropper (which can also pick a pixel in the Frame view). You can change between them until you are happy.
3. Press Apply, to the right of the Hex box. Nothing is added until you do. Press Esc to cancel.

If the colour is already in the palette, the program says "That colour is already in the palette. Choose a different colour." and stays in add mode. After Apply the program returns to normal; in Edit mode the Pencil is selected with the new colour.

### Deleting a colour

Right-click a palette square and choose Delete colour. A colour can be deleted only when no frame uses it, never the transparent colour, and not on the fixed-palette systems. The squares after it move up one place. Deleting can be undone. In Edit mode the same menu also offers Set as secondary colour.

### Eyedropper

Click the eyedropper, then a palette square or a pixel in the Frame view, to copy that colour into the preview square. It is switched on for you while you are adding a colour.

### The transparent colour

One palette colour is the project's **transparent colour**. It counts toward the system's colour maximum and is marked with a small white **T**. A new project uses magenta (#FF00FF).

- To change it, click the transparent colour box, then a palette square.
- It is shown as its real colour in the Frame view, previews and RunSpriteRun, so pick a colour you can see against your sprite.
- Exports and saved sheets use its real colour. No file the program writes ever carries an alpha channel, because the retro systems treat one palette colour as transparent.

### Fixed-palette systems

On the **Commodore 64** and **Apple II Double Hi-Res**, the 16 colours are set by the system. The colour editor is locked, and Reduce Palette is unavailable.

### Undo

Colour replacements and transparent colour changes can be undone.

## 7. Edit mode

Edit mode lets you draw and change sprites inside the program. Only colours already in the palette can be drawn, so a frame can never break the system's colour limits.

### Starting and leaving Edit mode

Use the **Edit mode** toggle in the Edit panel (under the palette). A box offers two choices:

- **Edit existing frame**: change the selected frame.
- **Create new frame**: add a frame as a copy of an existing frame, or as an empty frame (filled with the transparent colour), inserted before or after the current frame, or as frame 1.

In Edit mode the Frame view grows to a larger picture, and the Set Frame Group panel and RunSpriteRun window are hidden. The Frame Group Preview still plays. An orange border and an EDITING note show that you are editing, and other frames can be looked at but not drawn on.

Your edits are made on a working copy. When you switch Edit mode off, a box offers **Apply changes**, **Discard changes** (this also drops a new frame) or **Keep editing**. While editing, Undo and Redo step through your edits only. New, Open, Save, Save As, Export and closing the program ask you to leave Edit mode first.

### Layers

There are three layers: **ForeGround**, **Core** and **BackGround**. Each has an eye box (visible) and an X box (the layer your edits go to). You can tick several to edit them together. A hidden layer cannot be drawn on. A frame that was never edited, and any imported frame, has its picture on Core. When shown, saved or exported, the layers are flattened with ForeGround on top, then Core, then BackGround.

### Tools

Choose a tool in the Tools grid. The Options area shows only that tool's options. Tool letters work in Edit mode when you are not typing in a text box.

| Tool | Key | What it does | Options |
|---|---|---|---|
| Pencil | P | Click or drag to paint with the primary colour | Thickness; Pixel Perfect; square or round brush; Shift locks to a horizontal or vertical line |
| Eraser | E | Paints the transparent colour | Thickness; brush shape |
| Bucket | B | Fills an area with the primary colour | Contiguous or Global (every pixel of that colour); fill from the active layer only or all visible layers |
| Select | S | Drag a rectangle to select an area | Select All, Deselect, Cut, Copy, Paste, Delete |
| Move | M | Drags the selection, or the whole layer if nothing is selected | Works on every ticked layer |
| + Colour |  | Adds the colour from the colour editor to the next free palette slot | None; greyed out when the palette is full |
| Line | L | Draws a straight line | Thickness; brush shape; Shift locks to horizontal, vertical or 45 degrees |
| Square | R | Draws a rectangle | Thickness; Outline, Filled or Outline + Fill; draw from centre; Shift makes a true square |
| Circle | O | Draws an ellipse | Thickness; Outline, Filled or Outline + Fill; draw from centre; Shift makes a true circle |

Line, Square and Circle are pixel perfect at thickness 1, with no doubled corner pixels.

### Colours while drawing

- The **primary colour** (front square) is set by a left-click on the colour square, the picker or a palette square. The **secondary colour** (back square) is set by a right-click.
- Only Square and Circle use the secondary colour (for the fill in Outline + Fill).
- To use a new colour, add it with **+ Colour**. The tool then returns to the Pencil with the new colour selected.

### Actions row

Nine icons under the layers:

1. **Mirror vertically** and 2. **Mirror horizontally** are toggles. Click one, then click in the Frame view to place a yellow guide line. Pencil, Eraser, Line, Square and Circle then draw mirrored across the line. Use both for four-way symmetry. Click the icon again to switch it off.
2. **Rotate 90 degrees right**, 4. **Rotate 90 degrees left** and 5. **Rotate 180 degrees**. Rotating 90 degrees needs a square area.
3. **Flip horizontally** and 7. **Flip vertically**.
4. **Undo** and 9. **Redo**.

Rotate and flip act on the ticked layers, or on the selection or pasted piece if there is one.

### Selecting, copying and pasting

With the Select tool, drag a rectangle (dotted outline). **Ctrl+A** selects all, **Ctrl+C** copies, **Ctrl+X** cuts, **Ctrl+V** pastes and **Delete** clears. Paste lands at the top left as a floating piece that you can drag or nudge with the arrow keys; press **Enter** to fix it in place or **Esc** to discard it. The transparent colour is see-through when pasting. You can select and copy on a frame you are only viewing, to bring a piece from one frame to another.

### Zoom and pan

The mouse wheel zooms around the pointer, and the - and + buttons by the frame arrows do the same, from fit up to 64x. Hold **Space** and drag, or drag with the middle mouse button, to pan. The zoom stays when you step between frames.

## 8. The Edit menu: Undo, Shrink Sprite and Reduce Palette

The **Edit** menu holds **Undo** (Ctrl+Z), **Redo** (Ctrl+Y) and two tools that change the whole project at once: **Shrink Sprite** and **Reduce Palette**. Both are switched off while Edit mode is on.

**Important:** neither tool can be undone, and both ask you to confirm twice. They change every frame in the project. If you want to keep your original, use **File > Save As** first, or simply do not save after trying them. The program warns: "This cannot be undone. Do not save the project if you want to protect the original assets."

### Shrink Sprite

Makes every frame smaller by a percentage, and keeps the colours inside the project's palette.

1. Choose **Edit > Shrink Sprite**.
2. Pick a size: **87.5%, 75%, 50%, 25% or 12.5%**. The new frame size is shown.
3. Confirm. Each frame is scaled down by averaging, then every pixel is snapped back to the nearest colour in the project's palette, so the colour limit still holds.

A shrink that would take the frame below 4 pixels in either direction is refused. Shrinking clears the Undo history and marks the project as changed.

### Reduce Palette

Merges colours so the project uses fewer of them, for example to fit a tighter colour budget.

1. Choose **Edit > Reduce Palette**.
2. Choose how many colours to keep, from 2 up to one fewer than you have now. The transparent colour is not counted as one that can be merged away.
3. Look at the **From** and **To** previews. Use the frame spinner to check other frames.
4. Confirm.

The program joins the colours that are closest to each other, and the more heavily used colour survives. Every pixel of a removed colour becomes the nearest kept colour, in every frame. Reduce Palette is unavailable on the Commodore 64 and Apple II Double Hi-Res, whose palettes are fixed.

### Shorten Frame Names

Makes long frame names short. Frames from a sprite sheet are named after the sheet's file name, for example RickDangerous_SpriteSheet_Amiga_24x21_8x4_001. Choose Edit > Shorten Frame Names, type the text you want in place of the part every frame name starts with (for example Rick), and the frames become Rick_001, Rick_002 and so on. The new text cannot be empty and may use letters, numbers, - and _. A before and after example is shown, and the program asks you to confirm. It cannot be undone, so do not save if you want to keep the original names. When you import a sprite sheet, the Start Project box also has a Frame name box, filled with the file name, that you can shorten before you create the project.

### Group menu

**Group > New Group** (Ctrl+G) starts a new group in the Set Frame Group panel. **Group > Delete Group** removes the group shown after you confirm. Group > Frame Group Control opens the Frame Group Control window (the same as the Set Rules button). The Group menu is greyed out in Edit mode.

## 9. Saving, opening, exporting and settings

### Saving

A project is saved as one **.rsr** file inside its own project folder, for example Projects\DemoHero\DemoHero.rsr.

- **File > Save** (Ctrl+S) saves the whole project with no dialog.
- **File > Save As** saves a complete copy as a new project with a new name. Choose the parent folder (it starts at Projects) and a name. The dialog counts the characters as you type and warns you in orange if the name is too long (over 40 characters) or uses characters that are not allowed, and the OK button stays off until the name is valid.
- If you try to close the program or open another project with unsaved changes, it asks whether to save.

Each save writes, inside the project folder:

| Folder | What it holds |
|---|---|
| The project folder itself | The .rsr project file |
| Sprites | Every frame as its own PNG |
| Sprite_Sheet | One sprite sheet with all frames, and a .txt data file |
| Frame_Sprite_Sheets | One sprite sheet and data file for each Frame Group |
| The project folder itself | ProjectName_Rules.txt and ProjectName_Rules.json: the groups and key rules (see Export) |

Files from an earlier save that are no longer needed (for example after a frame is renamed) are cleaned up, and the program never deletes files it did not write. If a project was started from a sprite sheet, a copy of the original sheet is placed in the project folder on the first save.

### Opening a project

Use **File > Open Project** (Ctrl+O), or the Open Project button in the Start Project box. The dialog starts in your Projects folder. The ready-made examples live in the **Examples\Projects** folder next to it, one folder per system. A damaged file produces a message and never crashes the program.

### Project Information

**File > Project Information** shows a read-only summary: project name, file location, target system, colour limits, frame size, number of frames and groups, frames per second and colours in use (for example 11 / 16).

### Export

**File > Export** (Ctrl+E) writes finished image files for use in a game or another program. It never changes your project, and an unsaved project can be exported.

1. Choose the **Folder** (it starts at Exports). The program adds a folder named after your project.
2. Optionally choose the **Fill colour** for empty space in the sheets (it starts as the transparent colour).
3. Press **Export**.

Three folders are written: **Sprite_Sheet** (all frames), **Frame_Sprite_Sheets** (one per group) and **Sprites** (every frame as a PNG). If files already exist, the program lists them and asks whether to replace them. Frame files are named ProjectName_GroupName_FrameLabel.png, or NoGroup for a frame in no group.

Export also writes ProjectName_Rules.txt and ProjectName_Rules.json into the project's export folder, next to the three folders. The text file is tab-separated, so it opens in a spreadsheet: a table of the rules (priority, keys, only if in, the group each plays, loop or play once, and what happens on release) a table of the transitions, and a table of the groups (first and last frame, key, sprite sheet). The JSON file holds the same information for game developers, with the controller, the frames and file names of every group, and a short note on how to read the rules. Nothing in RunSpriteRun reads these files back. Save writes them into the project folder too, and File > Export Rules saves either file wherever you choose.

### Image rules

Every file written is a lossless **PNG with no alpha channel**. The transparent colour is saved as that colour. Nothing is ever scaled, smoothed or dithered: one sprite pixel is exactly one pixel in the file.

### Sprite sheet layout

Saved and exported sheets use the same layout as a blank sheet, so a sheet can be imported again. Each sprite sits in its own box, outlined in a box colour (bright green unless your sprites use it), ten boxes to a row. A text bar runs along the top, and a colour bar under the boxes shows one swatch for each palette colour. Saved sheets also have a small .txt file listing each frame's number, label, group and position.

### Create Blank Sprite Sheet

**File > Create Blank Sprite Sheet** makes an empty sheet to draw on in another art program. It works with or without a project open. Choose the **System**, the **Sprite width** and **height** (4 to 128), **Sprites per row** and **Number of rows**, then the **Box colour** (default #00FF00) and **Transparent colour** (default #FF00FF), and press **Create**. The limits are 120 sprites and a sheet no wider than 2,048 pixels. The box colour and transparent colour must differ. Draw inside the boxes without using the box colour, then import the finished sheet in the Start Project box. Blank sheets are saved in the **Blank sprite sheets** folder, in a folder per system.

### Settings

**File > Settings** (Ctrl+,) is available while a project is open. It sets **Frames per second** (3, 6, 12 or 24) for that project. The change takes effect at once, even while RunSpriteRun is running, and can be undone. The program is always dark, and the sprite views always have a black background.

### About and Help

**Help** (F1) opens the built-in help. **About** shows the version and author.

## 10. Reference

### Keyboard shortcuts

| Shortcut | What it does | Where |
|---|---|---|
| Ctrl+N | New project (opens Start Project) | Anywhere |
| Ctrl+O | Open project | Anywhere |
| Ctrl+S | Save | Anywhere |
| Ctrl+E | Export | Anywhere |
| Ctrl+, | Settings | Anywhere, with a project open |
| Ctrl+Z / Ctrl+Y | Undo / Redo | Anywhere (in Edit mode they step through your edits) |
| Ctrl+G | New group | Anywhere |
| F1 | Help | Anywhere |
| Esc | Stop RunSpriteRun (while it is running) | Normal mode |
| W A S D, 1 to 6, 7 8 9 0 | Play the group assigned to the key | While RunSpriteRun is running |
| Ctrl+C / Ctrl+V | Copy / paste frames | Timeline has the focus |
| Ctrl+Left / Ctrl+Right | Move the selected frame one place | Timeline has the focus |
| Ctrl+click / Shift+click | Add to / select a range of frames | Timeline |
| Delete | Delete the selected frames | Timeline has the focus |
| P E B S M L R O | Pencil, Eraser, Bucket, Select, Move, Line, Square, Circle | Edit mode |
| Ctrl+A / X / C / V, Delete | Select all, cut, copy, paste, clear | Select tool, Edit mode |
| Enter / Esc | Fix / discard a pasted piece | Edit mode |
| Shift (while drawing) | Lock to a straight line, square or circle | Edit mode |
| Mouse wheel, Space+drag | Zoom, pan | Edit mode |

### Limits

| Item | Limit |
|---|---|
| Frame size | 4 x 4 to 128 x 128 pixels |
| Frames per project | 120 |
| Frame groups per project | 32 |
| Project name | 1 to 40 characters (letters, numbers, - and _) |
| Group name | 1 to 20 characters |
| Frame label name | 1 to 60 characters |
| Sprite colours | 16 or 32, set by the system, including the transparent colour |
| Blank sprite sheet | 120 sprites, up to 2,048 pixels wide |
| Frames per second | 3, 6, 12 or 24 |
| Image formats in | PNG, BMP, GIF (no transparency, no animated GIFs) |
| Image format out | PNG, 24-bit, no alpha |

### Example projects

Ten ready-made projects are installed in the **Examples\Projects** folder, one folder per system. Each is named System_Game_Example, for example AtariST_Gods_Example, and holds the project file, its Sprites, Sprite_Sheet and Frame_Sprite_Sheets folders, and (where it was made from one) the original source sheet. Open one with **File > Open Project** and browse to the Examples folder. A README.txt in the Examples folder lists them. Your changes to an example are saved only if you press Save, so use Save As to keep your own copy.

### Troubleshooting

**"Maximum frames exceeded on import".** Choose 120 files or fewer.

**A file is skipped on import.** The message names the file and the reason: wrong size, transparency (alpha) in the file, or too many colours for the system. Fix the file in your art program and import it again.

**"More colours in file than available for selected system".** Reduce the colours in the picture before importing, or choose a system with a larger palette.

**My sprite sheet is refused.** Check that the box lines are in the Box colour you chose, that every box is the same size (4 to 128 pixels), that the Box colour and Transparent colour differ, and that the sheet has no see-through pixels.

**Keys do nothing in RunSpriteRun.** Make sure the key has a group, or is used by a rule in Frame Group Control, and click away from any text box.

A Frame Group Control rule never plays. Rules are checked from the top, so a rule higher up that needs fewer keys (such as D) can win before a rule that needs more (such as W+D+1). Use the arrows to move the more specific rule up.

**"Switch back to RunSpriteRun mode first."** Turn Edit mode off (apply or discard your changes), then save, open or export.

**I shrunk or reduced a project by mistake.** Those two tools cannot be undone. Close the project without saving, and open the saved version again.

**The Save As name is orange.** The name is over 40 characters or contains a space or symbol. Shorten it or remove the characters.

**Colours look different from my art program.** The program snaps every colour to the nearest one the chosen system can display. That is deliberate: what you see is what the system could show.

### Privacy and licence

RunSpriteRun is offline: it makes no network connections and collects nothing. It is free software released under the MIT licence. The source code is on GitHub (hlehmann-git/RunSpriteRun). Made by Harley Lehmann.
