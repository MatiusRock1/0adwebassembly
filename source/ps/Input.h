/* Copyright (C) 2026 Wildfire Games.
 * This file is part of 0 A.D.
 *
 * 0 A.D. is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 2 of the License, or
 * (at your option) any later version.
 *
 * 0 A.D. is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with 0 A.D.  If not, see <http://www.gnu.org/licenses/>.
 */

#ifndef INCLUDED_INPUT_HANDLER
#define INCLUDED_INPUT_HANDLER

#include "ps/Input.h"

#include <array>
#include <concepts>
#include <cstddef>
#include <queue>
#include <memory>
#include <optional>
#include <type_traits>

class ScriptRequest;
union SDL_Event;

namespace Input
{
class HandlerBase;

enum class Reaction
{
	// Pass the event to the next handler in the chain.
	PASS,

	// We handled it. No other handlers will receive this event.
	HANDLED
};

// A slot for each handler. Numbers are in invocation order. A handler can discard events. The first handler
// is the only which gets all events.
namespace Slot
{
constexpr std::integral_constant<std::size_t, 0> PRIMARY;
constexpr std::integral_constant<std::size_t, 1> WINDOW;
constexpr std::integral_constant<std::size_t, 2> SCREENSHOT;

// These two must be called first `globalsInput` deals with some important global state, such as which
// scancodes are being pressed, mouse buttons pressed, etc. while hotkeyStateChange updates the map of
// active hotkeys.
constexpr std::integral_constant<std::size_t, 3> HOTKEY_STATE_CHANGE;
constexpr std::integral_constant<std::size_t, 4> GLOBAL;

// Should be called after scancode map update (i.e. after the global input, but before UI). This never
// blocks the event, but it does some processing necessary for hotkeys, which are triggered later down the
// input chain. (by calling this before the UI, we can use `EventWouldTriggerHotkey` in the UI).
constexpr std::integral_constant<std::size_t, 5> HOTKEY_INPUT_PREPARATION;

constexpr std::integral_constant<std::size_t, 6> TOUCH_INPUT;

// The console handler needs to be called before the hotkey handler so that text can be typed in without
// setting off hotkeys.
constexpr std::integral_constant<std::size_t, 7> CONSOLE;
// Likewise for gui.
constexpr std::integral_constant<std::size_t, 8> GUI;
constexpr std::integral_constant<std::size_t, 9> HOTKEY_INPUT;
constexpr std::integral_constant<std::size_t, 10> PROFILE_VIEWER;
constexpr std::integral_constant<std::size_t, 11> GAME_VIEW;
}

/**
 * Holds a pointer to all registered `HandlerBase`s.
 * It does unregister all registered `Handler`s in the destructor.
 */
class Manager
{
public:
	Manager();
	// The `Manager` needs to have a constant memory location (the `Handler`s hold a pointer to it).
	Manager(Manager&) = delete;
	Manager& operator=(Manager&) = delete;
	Manager(Manager&&) = delete;
	Manager& operator=(Manager&&) = delete;
	~Manager();

	void PushPriorityEvent(const SDL_Event& event);
	void DispatchEvent(const SDL_Event& event);

	template<std::size_t slot>
	HandlerBase*& Get() noexcept
	{
		return std::get<slot>(m_Handlers);
	}

	class PollEventsResult
	{
	public:
		class EventIterator
		{
		public:
			using difference_type = std::ptrdiff_t;
			using value_type = SDL_Event;
			using pointer = value_type*;
			using reference = value_type&;
			using iterator_category = std::input_iterator_tag;

			EventIterator() = default;
			explicit EventIterator(PollEventsResult& range);

			reference operator*();
			pointer operator->();

			EventIterator& operator++();
			EventIterator& operator++(int);

			bool operator==(const EventIterator& other) const;

		private:
			PollEventsResult* m_Storage{nullptr};
		};

		explicit PollEventsResult(std::queue<SDL_Event>& priorityEvents);

		EventIterator begin();
		EventIterator end();

	private:
		std::queue<SDL_Event>& m_PriorityEvents;
		const std::unique_ptr<SDL_Event> m_Event;
	};

	PollEventsResult PollEvents();

private:
	std::array<HandlerBase*, 12> m_Handlers{{}};
	const std::unique_ptr<std::queue<SDL_Event>> m_PriorityEvents;
};

/**
 * Type-erased callable
 */
class HandlerBase
{
protected:
	/**
	 * Can't not be constructed themself, use `Handler` instead.
	 * @param pos On construction the pointer is set to @c this. On
	 *	destruction the pointer will be set to nullptr.
	 */
	explicit HandlerBase(HandlerBase*& pos) noexcept;
	virtual ~HandlerBase();

	// A `HandlerBase` needs to have a constant memory location (the `Manager` does hold a pointer to it).
	HandlerBase(HandlerBase&) = delete;
	HandlerBase& operator=(HandlerBase&) = delete;
	HandlerBase(HandlerBase&&) = delete;
	HandlerBase& operator=(HandlerBase&&) = delete;

public:
	virtual Input::Reaction operator()(const SDL_Event& event) = 0;

private:
	// When the handler is destructed this position han to be changed to
	// `nullptr`, so that it's not invoked again.
	HandlerBase*& m_ToReset;
};

/**
 * Usable type to register a handler to the associated `Manager`.
 */
template<std::invocable<const SDL_Event&> Callback>
class Handler final : private HandlerBase
{
public:
	// `slot` specifies when(in which order) the `callback` of this `Handler` is executed.
	template<std::size_t slot>
	explicit Handler(Manager& manager, std::integral_constant<std::size_t, slot>, Callback func) :
		HandlerBase{manager.Get<slot>()},
		m_Callback{std::move(func)}
	{
	}
	~Handler() final = default;

private:
	Input::Reaction operator()(const SDL_Event& event) final
	{
		return m_Callback(event);
	}

	Callback m_Callback;
};
}

#endif // INCLUDED_INPUT_HANDLER
