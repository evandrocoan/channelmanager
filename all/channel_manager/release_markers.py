"""Validate historical Sublime build markers independently of the channel runtime."""

import re


_MARKER_REF = re.compile(r"^st-build-(\d{4})$")
_VERSION = re.compile(r"^\d+\.\d+$")
_CEILING = re.compile(r"^([<>]=?)(\d{4})$")
_INTERVAL = re.compile(r"^(\d{4}) - (\d{4})$")


def _selector_bounds(selector):
    if not isinstance(selector, str):
        raise ValueError("A build marker needs a sublime_text selector")

    match = _CEILING.fullmatch(selector)
    if match:
        operator, build = match.groups()
        if operator == "<=":
            return 0, int(build)
        if operator == "<":
            return 0, int(build) - 1
        raise ValueError("A historical selector needs a finite upper build: %s" % selector)

    match = _INTERVAL.fullmatch(selector)
    if match:
        lower, upper = (int(value) for value in match.groups())
        if lower <= upper:
            return lower, upper

    raise ValueError("Invalid historical sublime_text selector: %s" % selector)


def parse_release_markers(tags):
    """Return the current-release ref and validated historical marker entries."""
    if tags is None:
        return None, []
    if not isinstance(tags, list):
        raise ValueError("tags must be a list")

    current_ref = None
    markers = []
    seen_refs = set()

    for tag in tags:
        if isinstance(tag, str):
            if tag.isdigit():
                raise ValueError("A numeric build ref needs an explicit marker selector: %s" % tag)
            if not tag or tag.startswith("st-build-") or current_ref is not None:
                raise ValueError("Invalid or duplicate current-release ref: %s" % tag)
            current_ref = tag
            continue

        if not isinstance(tag, dict) or set(tag) != {"ref", "sublime_text", "python_versions"}:
            raise ValueError("Each build marker needs ref, sublime_text and python_versions")

        ref = tag["ref"]
        match = _MARKER_REF.fullmatch(ref) if isinstance(ref, str) else None
        if not match or ref in seen_refs:
            raise ValueError("Invalid or duplicate build marker ref: %s" % ref)

        host_versions = tag["python_versions"]
        if (not isinstance(host_versions, list) or not host_versions
                or any(not isinstance(host, str) or not _VERSION.fullmatch(host)
                       for host in host_versions)
                or len(host_versions) != len(set(host_versions))):
            raise ValueError("Invalid python_versions for %s" % ref)

        build = int(match.group(1))
        lower, upper = _selector_bounds(tag["sublime_text"])
        generation = build // 1000
        generation_start = 0 if generation == 3 else generation * 1000
        generation_end = generation * 1000 + 999

        if (generation < 3 or lower < generation_start or upper > generation_end
                or not lower <= build <= upper):
            raise ValueError("Selector for %s is outside its Sublime generation" % ref)

        marker = dict(tag)
        marker["ceiling"] = upper
        markers.append(marker)
        seen_refs.add(ref)

    return current_ref, markers


def mutable_release_tags(tags):
    """Exclude Sublime build markers and ST3 releases from automatic tag cleanup."""
    return [tag for tag in tags if tag and not tag.isdigit()
            and not tag.startswith(("st-build-", "st3-"))]


def latest_semantic_tag(tags):
    """Return the latest sorted semantic ref, or the branch fallback."""
    semantic_tags = [tag for tag in tags if re.match(r"^(\d+)\.(\d+)(.+)?$", tag)]
    return semantic_tags[-1] if semantic_tags else "master"


def declared_main_branch(branch_mappings):
    """Use the fork branch recorded in .gitmodules when a repo has no release tag."""
    if isinstance(branch_mappings, str):
        for mapping in branch_mappings.split(","):
            if "->" in mapping:
                branch = mapping.split("->", 1)[1].strip()
                if branch:
                    return branch
    return "master"
