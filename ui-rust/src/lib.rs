use std::cell::RefCell;
use std::rc::Rc;

use wasm_bindgen::closure::Closure;
use wasm_bindgen::prelude::*;
use wasm_bindgen::JsCast;
use web_sys::{
    Document, Element, Event, EventInit, HtmlButtonElement, HtmlElement, HtmlOptionElement,
    HtmlSelectElement, KeyboardEvent, MutationObserver, MutationObserverInit,
};

struct Select {
    original: HtmlSelectElement,
    button: HtmlButtonElement,
    menu: HtmlElement,
    value: HtmlElement,
    typed: RefCell<(String, f64)>,
}

thread_local! {
    static CONTROLS: RefCell<Vec<Rc<Select>>> = const { RefCell::new(Vec::new()) };
}

fn document() -> Document {
    web_sys::window().unwrap().document().unwrap()
}

fn attr(element: &Element, name: &str, value: &str) {
    let _ = element.set_attribute(name, value);
}

fn js_method(element: &Element, name: &str) {
    if let Ok(value) = js_sys::Reflect::get(element, &JsValue::from_str(name)) {
        if let Some(function) = value.dyn_ref::<js_sys::Function>() {
            let _ = function.call0(element);
        }
    }
}

fn sync(control: &Select) {
    control.button.set_disabled(control.original.disabled());
    let options = control.original.options();
    let selected = control.original.selected_index();
    let text = u32::try_from(selected)
        .ok()
        .and_then(|i| options.item(i))
        .and_then(|node| node.text_content())
        .unwrap_or_else(|| "Выберите значение".into());
    control.value.set_text_content(Some(&text));
    control.menu.set_text_content(None);
    for i in 0..options.length() {
        let Some(option) = options
            .item(i)
            .and_then(|v| v.dyn_into::<HtmlOptionElement>().ok())
        else {
            continue;
        };
        let item: HtmlButtonElement = document()
            .create_element("button")
            .unwrap()
            .unchecked_into();
        item.set_type("button");
        item.set_class_name("material-select-option");
        item.set_disabled(option.disabled());
        item.set_tab_index(-1);
        attr(&item, "role", "option");
        attr(&item, "data-index", &i.to_string());
        attr(
            &item,
            "aria-selected",
            if option.selected() { "true" } else { "false" },
        );
        let label = document().create_element("span").unwrap();
        label.set_text_content(option.text_content().as_deref());
        let check = document().create_element("span").unwrap();
        check.set_class_name("material-select-check");
        attr(&check, "aria-hidden", "true");
        check.set_text_content(Some("✓"));
        let _ = item.append_child(&label);
        let _ = item.append_child(&check);
        let _ = control.menu.append_child(&item);
    }
}

fn position(control: &Select) {
    let window = web_sys::window().unwrap();
    let rect = control.button.get_bounding_client_rect();
    let vw = window.inner_width().unwrap().as_f64().unwrap();
    let vh = window.inner_height().unwrap().as_f64().unwrap();
    let width = rect.width().max(260.0).min(vw - 24.0);
    let below = vh - rect.bottom() - 12.0;
    let above = rect.top() - 12.0;
    let down = below >= 336.0 || below >= above;
    let height = (if down { below } else { above } - 6.0).clamp(0.0, 336.0);
    let left = rect.left().min(vw - width - 12.0).max(12.0);
    let top = if down {
        rect.bottom() + 6.0
    } else {
        (rect.top() - height - 6.0).max(12.0)
    };
    let style = control.menu.style();
    let _ = style.set_property("width", &format!("{width}px"));
    let _ = style.set_property("max-height", &format!("{height}px"));
    let _ = style.set_property("left", &format!("{left}px"));
    let _ = style.set_property("top", &format!("{top}px"));
}

fn focus_option(control: &Select, mode: i32) {
    let list = control
        .menu
        .query_selector_all("[role=option]:not(:disabled)")
        .unwrap();
    let count = list.length() as i32;
    if count == 0 {
        return;
    }
    let active = document().active_element();
    let mut focused = -1;
    let mut selected = 0;
    for i in 0..count {
        let item: Element = list.item(i as u32).unwrap().unchecked_into();
        if active.as_ref() == Some(&item) {
            focused = i;
        }
        if item.get_attribute("aria-selected").as_deref() == Some("true") {
            selected = i;
        }
    }
    let index = match mode {
        2 => 0,
        -2 => count - 1,
        _ if focused < 0 => selected,
        _ => (focused + mode + count) % count,
    };
    if let Some(item) = list
        .item(index as u32)
        .and_then(|v| v.dyn_into::<HtmlElement>().ok())
    {
        let _ = item.focus();
        let options = web_sys::ScrollIntoViewOptions::new();
        options.set_block(web_sys::ScrollLogicalPosition::Nearest);
        item.scroll_into_view_with_scroll_into_view_options(&options);
    }
}

fn on(target: &web_sys::EventTarget, name: &str, f: impl FnMut(Event) + 'static) {
    let callback = Closure::<dyn FnMut(Event)>::new(f);
    target
        .add_event_listener_with_callback(name, callback.as_ref().unchecked_ref())
        .unwrap();
    callback.forget();
}

fn create(id: &str, label: &str) {
    let doc = document();
    let select: HtmlSelectElement = doc.get_element_by_id(id).unwrap().unchecked_into();
    let menu: HtmlElement = doc.create_element("div").unwrap().unchecked_into();
    if !js_sys::Reflect::has(&menu, &JsValue::from_str("showPopover")).unwrap_or(false) {
        return;
    }
    let button: HtmlButtonElement = doc.create_element("button").unwrap().unchecked_into();
    button.set_type("button");
    button.set_class_name("material-select-trigger");
    attr(&button, "aria-label", label);
    attr(&button, "aria-haspopup", "listbox");
    attr(&button, "aria-expanded", "false");
    attr(&button, "aria-controls", &format!("{id}-menu"));
    let value: HtmlElement = doc.create_element("span").unwrap().unchecked_into();
    value.set_class_name("material-select-value");
    let arrow = doc.create_element("span").unwrap();
    arrow.set_class_name("material-select-arrow");
    attr(&arrow, "aria-hidden", "true");
    let _ = button.append_child(&value);
    let _ = button.append_child(&arrow);
    menu.set_id(&format!("{id}-menu"));
    menu.set_class_name("material-select-menu");
    attr(&menu, "popover", "auto");
    attr(&menu, "role", "listbox");
    attr(&menu, "aria-label", label);
    select
        .parent_node()
        .unwrap()
        .insert_before(&button, select.next_sibling().as_ref())
        .unwrap();
    doc.body().unwrap().append_child(&menu).unwrap();
    select.set_hidden(true);
    let control = Rc::new(Select {
        original: select,
        button,
        menu,
        value,
        typed: RefCell::new((String::new(), 0.0)),
    });
    sync(&control);

    let c = Rc::clone(&control);
    on(&control.button, "click", move |_| {
        sync(&c);
        position(&c);
        js_method(&c.menu, "showPopover");
        position(&c);
        focus_option(&c, 0);
    });
    let c = Rc::clone(&control);
    on(&control.button, "keydown", move |event| {
        let Some(key) = event.dyn_ref::<KeyboardEvent>() else {
            return;
        };
        if key.key() == "ArrowDown" || key.key() == "ArrowUp" {
            event.prevent_default();
            sync(&c);
            position(&c);
            js_method(&c.menu, "showPopover");
            position(&c);
            focus_option(&c, 0);
        }
    });
    let c = Rc::clone(&control);
    on(&control.menu, "toggle", move |_| {
        attr(
            &c.button,
            "aria-expanded",
            if c.menu.matches(":popover-open").unwrap_or(false) {
                "true"
            } else {
                "false"
            },
        );
    });
    let c = Rc::clone(&control);
    on(&control.menu, "click", move |event| {
        let Some(target) = event.target().and_then(|v| v.dyn_into::<Element>().ok()) else {
            return;
        };
        let Some(item) = target.closest("[data-index]").ok().flatten() else {
            return;
        };
        let Some(index) = item
            .get_attribute("data-index")
            .and_then(|v| v.parse::<i32>().ok())
        else {
            return;
        };
        c.original.set_selected_index(index);
        let init = EventInit::new();
        init.set_bubbles(true);
        for kind in ["input", "change"] {
            let _ = c
                .original
                .dispatch_event(&Event::new_with_event_init_dict(kind, &init).unwrap());
        }
        js_method(&c.menu, "hidePopover");
        let _ = c.button.focus();
    });
    let c = Rc::clone(&control);
    on(&control.menu, "keydown", move |event| {
        let Some(key) = event.dyn_ref::<KeyboardEvent>() else {
            return;
        };
        match key.key().as_str() {
            "ArrowDown" => {
                event.prevent_default();
                focus_option(&c, 1);
            }
            "ArrowUp" => {
                event.prevent_default();
                focus_option(&c, -1);
            }
            "Home" => {
                event.prevent_default();
                focus_option(&c, 2);
            }
            "End" => {
                event.prevent_default();
                focus_option(&c, -2);
            }
            "Escape" => {
                event.prevent_default();
                js_method(&c.menu, "hidePopover");
                let _ = c.button.focus();
            }
            "Tab" => {
                js_method(&c.menu, "hidePopover");
                let _ = c.button.focus();
            }
            value
                if value.chars().count() == 1
                    && !key.ctrl_key()
                    && !key.meta_key()
                    && !key.alt_key() =>
            {
                let now = js_sys::Date::now();
                let mut typed = c.typed.borrow_mut();
                if now - typed.1 > 700.0 {
                    typed.0.clear();
                }
                typed.0.push_str(&value.to_lowercase());
                typed.1 = now;
                let list = c
                    .menu
                    .query_selector_all("[role=option]:not(:disabled)")
                    .unwrap();
                for i in 0..list.length() {
                    if let Some(item) = list.item(i).and_then(|v| v.dyn_into::<HtmlElement>().ok())
                    {
                        if item
                            .text_content()
                            .unwrap_or_default()
                            .trim()
                            .to_lowercase()
                            .starts_with(&typed.0)
                        {
                            event.prevent_default();
                            let _ = item.focus();
                            let options = web_sys::ScrollIntoViewOptions::new();
                            options.set_block(web_sys::ScrollLogicalPosition::Nearest);
                            item.scroll_into_view_with_scroll_into_view_options(&options);
                            break;
                        }
                    }
                }
            }
            _ => {}
        }
    });
    let c = Rc::clone(&control);
    let observer_callback =
        Closure::<dyn FnMut(JsValue, MutationObserver)>::new(move |_, _| sync(&c));
    let observer = MutationObserver::new(observer_callback.as_ref().unchecked_ref()).unwrap();
    let options = MutationObserverInit::new();
    options.set_child_list(true);
    options.set_subtree(true);
    options.set_attributes(true);
    let _ = observer.observe_with_options(&control.original, &options);
    observer_callback.forget();
    CONTROLS.with(|controls| controls.borrow_mut().push(control));
}

#[wasm_bindgen]
pub fn sync_material_selects() {
    CONTROLS.with(|controls| {
        for control in controls.borrow().iter() {
            sync(control);
        }
    });
}

#[wasm_bindgen(start)]
pub fn start() {
    create("dub-direction", "Язык перевода");
    create("dub-provider", "Переводчик");
    create("dub-format", "Формат API");
    let callback = Closure::<dyn FnMut()>::new(sync_material_selects);
    let _ = js_sys::Reflect::set(
        &web_sys::window().unwrap(),
        &JsValue::from_str("syncMaterialSelects"),
        callback.as_ref(),
    );
    callback.forget();
    let window = web_sys::window().unwrap();
    on(&window, "resize", |_| {
        CONTROLS.with(|controls| {
            for c in controls.borrow().iter() {
                if c.menu.matches(":popover-open").unwrap_or(false) {
                    position(c);
                }
            }
        })
    });
    let callback = Closure::<dyn FnMut(Event)>::new(|event: Event| {
        CONTROLS.with(|controls| {
            for control in controls.borrow().iter() {
                if !control.menu.matches(":popover-open").unwrap_or(false) {
                    continue;
                }
                let target = event
                    .target()
                    .and_then(|value| value.dyn_into::<web_sys::Node>().ok());
                if target
                    .as_ref()
                    .is_none_or(|node| !control.menu.contains(Some(node)))
                {
                    position(control);
                }
            }
        });
    });
    document()
        .add_event_listener_with_callback_and_bool(
            "scroll",
            callback.as_ref().unchecked_ref(),
            true,
        )
        .unwrap();
    callback.forget();
}
